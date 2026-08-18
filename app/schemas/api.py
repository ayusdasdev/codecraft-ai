from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, SecretStr

from app.schemas.agent import Plan, TaskPlan


class JobStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    ARCHITECTING = "architecting"
    CODING = "coding"
    DONE = "done"
    FAILED = "failed"

class PlanRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    groq_api_key: Optional[SecretStr] = Field(default=None)

class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    groq_api_key:  Optional[SecretStr] = Field(default=None)

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    plan: Optional[Plan] = None
    task_plan: Optional[TaskPlan] = None
    error: Optional[str] = None


