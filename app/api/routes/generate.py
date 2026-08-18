from fastapi import APIRouter, Depends, status

from app.api.deps import get_job_manager
from app.schemas.api import GenerateRequest
from app.services.job_manager import JobManager

router = APIRouter()


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def start_generation(
    payload: GenerateRequest,
    job_manager: JobManager = Depends(get_job_manager),
):
    record = await job_manager.create_job(payload.prompt, payload.groq_api_key)
    return {"job_id": record.job_id, "status": record.status}