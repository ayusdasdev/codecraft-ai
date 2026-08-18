import logging
from fastapi import APIRouter, HTTPException
from app.core.config import get_settings
from app.schemas.agent import Plan
from app.schemas.api import PlanRequest
from app.services.agent_graph import create_llm, planner_prompt


router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/plan", response_model=Plan)
async def create_plan(payload: PlanRequest):
    settings = get_settings()
    api_key = payload.groq_api_key or settings.groq_api_key

    try:
        llm = create_llm(api_key, settings.groq_model)
        chain = planner_prompt | llm.with_structured_output(Plan, method="json_mode")
        return await chain.ainvoke({"user_prompt": payload.prompt})
    except Exception:
        logger.exception("Planner LLM call failed")
        raise HTTPException(status_code=502, detail="Planner LLM call failed. Please try again.")