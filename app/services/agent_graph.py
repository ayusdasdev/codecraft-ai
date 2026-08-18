import time
from typing import TypedDict, Optional, Callable

from groq import RateLimitError, BadRequestError
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import SecretStr

from app.schemas.agent import Plan, TaskPlan, ArchitectOutput


def create_llm(api_key: SecretStr, model: str, temperature: float = 0.2) -> ChatGroq:
    """Factory for a configured ChatGroq instance -- one place to change provider/defaults later"""
    return ChatGroq(model=model, api_key=api_key, temperature=temperature)

class AgentState(TypedDict):
    user_prompt: str
    plan: Optional[Plan]
    task_plan: Optional[TaskPlan]
    current_step_idx: int
    status: str

PLANNER_SYSTEM_PROMPT = """You are a product planner. Given a one-line app idea, produce a
concise plan: a name, a one-sentence description, 3-5 core features, and a suggested tech stack.
Keep it focused -- this plan will be handed to an architect to break into implementation steps.

Respond with a valid JSON object with exactly this shape:
{{"name": "...", "description": "...", "features": ["..."], "tech_stack": ["..."]}}"""

planner_prompt = ChatPromptTemplate.from_messages([
    ("system", PLANNER_SYSTEM_PROMPT),
    ("human","{user_prompt}")
])

def planner_node(state: AgentState, llm) -> dict:
    chain = planner_prompt | llm.with_structured_output(Plan, method = "json_mode")
    plan = chain.invoke({"user_prompt": state["user_prompt"]})
    return {"plan": plan, "status": "architecting"}

ARCHITECT_SYSTEM_PROMPT = """You are a senior software architect. Given a product plan, break
it into a numbered, ordered list of concrete implementation steps. Each step must be small enough
to implement in a single file and should list which file(s) it creates. Do not write any code --
only describe what needs to be built, in order. Do not include testing or deployment steps.

Respond with a valid JSON object with exactly this shape:
{{"implementation_steps": [{{"step_number": 1, "description": "...", "files_to_create": ["..."]}}]}}"""

architect_prompt = ChatPromptTemplate.from_messages([
    ("system", ARCHITECT_SYSTEM_PROMPT),
    ("human", "Plan name: {name}\nDescription: {description}\nFeatures: {features}\nTech stack: {tech_stack}"),
])
def architect_node(state: AgentState, llm) -> dict:
    plan = state["plan"]
    chain = architect_prompt | llm.with_structured_output(ArchitectOutput, method="json_mode")
    output = chain.invoke({
        "name": plan.name,
        "description": plan.description,
        "features": ", ".join(plan.features),
        "tech_stack": ", ".join(plan.tech_stack),
    })
    task_plan = TaskPlan(plan=plan, implementation_steps=output.implementation_steps)
    return {"task_plan": task_plan, "current_step_idx": 0, "status": "coding"}

MAX_RETRIES = 3

CODER_SYSTEM_PROMPT = """You are a careful software engineer implementing one step of a larger
plan. You have EXACTLY these four tools available, and no others:
- read_file(relative_path): read a file's contents
- write_file(relative_path, content): write/overwrite a file
- list_files(relative_path="."): list files and directories at a path
- get_current_directory(): get the project root's absolute path

There is no search tool, no repo browser, no "commentary" tool, and no tool to explore, search,
or act on the codebase other than these four. If you want to see what files exist anywhere in
the project, call list_files. If you want to see a file's contents, call read_file. If you want
to write or overwrite a file, call write_file. If you need to know the project's root path, call
get_current_directory. Do not attempt to call any tool not in this exact list of four, even if
it seems like it should exist -- if you are unsure whether a tool exists, assume it does not and
use one of these four instead.

Use list_files before writing a new file, so you don't accidentally overwrite unrelated work
from a previous step. Write complete, working code -- do not leave TODO placeholders or partial
implementations. When you have finished writing the file(s) required for this step, stop -- do
not attempt extra steps beyond what was asked."""


def coder_node(state: AgentState, llm, tools: list, project_root) -> dict:
    steps = state["task_plan"].implementation_steps
    idx = state["current_step_idx"]
    if idx >= len(steps):
        return {"status": "done"}
    step = steps[idx]
    react_agent = create_react_agent(llm, tools, prompt=CODER_SYSTEM_PROMPT)
    instruction = f"Implement step {step.step_number}: {step.description}. " \
                  f"Files to create: {', '.join(step.files_to_create)}."
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            react_agent.invoke({"messages": [("user", instruction)]})

            missing = [f for f in step.files_to_create if not (project_root / f).exists()]
            if missing:
                last_error = f"Agent finished but did not create: {missing}"
                if attempt < MAX_RETRIES:
                    continue
                raise RuntimeError(last_error)

            return {"current_step_idx": idx + 1}
        except RateLimitError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
        except BadRequestError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                continue
    raise RuntimeError(f"Step {step.step_number} failed after {MAX_RETRIES} attempts: {last_error}")

def route_after_coding(state: AgentState) -> str:
    return "done" if state["status"] == "done" else "continue"


def build_graph(llm, tools: list, project_root):
    builder = StateGraph(AgentState)
    builder.add_node("planner", lambda state: planner_node(state, llm))
    builder.add_node("architect", lambda state: architect_node(state, llm))
    builder.add_node("coder", lambda state: coder_node(state, llm, tools, project_root))
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "architect")
    builder.add_edge("architect", "coder")
    builder.add_conditional_edges(
        "coder",
        route_after_coding,
        {"continue": "coder", "done": END},
    )
    return builder.compile()
OnEvent = Optional[Callable[[str, dict], None]]
def run_agent_streaming(graph: CompiledStateGraph, user_prompt: str, on_event: OnEvent = None):
    initial_state = {
        "user_prompt": user_prompt,
        "plan": None,
        "task_plan": None,
        "current_step_idx": 0,
        "status": "planning",
    }
    final_state = dict(initial_state)
    for step_output in graph.stream(initial_state, {"recursion_limit": 100}): # type: ignore[arg-type]
        for node_name, node_state in step_output.items():
            final_state.update(node_state)
            if on_event:
                on_event(node_name, final_state)
    return final_state


