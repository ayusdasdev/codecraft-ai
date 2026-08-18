from pydantic import BaseModel, Field


class Plan(BaseModel):
    name: str = Field(description="The name of the app to be built")
    description: str = Field(description="A short summary of what it does")
    features: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)

class ImplementationStep(BaseModel):
    step_number: int
    description: str
    files_to_create: list[str] = Field(default_factory=list)

class TaskPlan(BaseModel):
    plan: Plan
    implementation_steps: list[ImplementationStep] = Field(default_factory=list)

class ArchitectOutput(BaseModel):
    implementation_steps: list[ImplementationStep] = Field(default_factory=list)