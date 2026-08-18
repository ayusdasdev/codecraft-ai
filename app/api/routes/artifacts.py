import asyncio
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_job_manager
from app.services.job_manager import JobManager
from app.services.storage import get_s3_client, generate_presigned_url
from app.core.config import get_settings

router = APIRouter()


@router.get("/artifacts/{job_id}")
async def get_artifacts(job_id: str, job_manager: JobManager = Depends(get_job_manager)):
    record = job_manager.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not record.s3_bucket:
        raise HTTPException(status_code=409, detail="No artifacts available for this job")

    settings = get_settings()
    client = get_s3_client(settings.aws_region)

    def build_urls():
        zip_url = generate_presigned_url(client, record.s3_bucket, record.s3_zip_key)
        file_urls = {
            key: generate_presigned_url(client, record.s3_bucket, key)
            for key in record.s3_file_keys
        }
        return zip_url, file_urls

    zip_url, file_urls = await asyncio.to_thread(build_urls)
    return {"zip_url": zip_url, "files": file_urls}