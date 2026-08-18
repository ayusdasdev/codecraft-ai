from fastapi import Request
from app.services.job_manager import JobManager


def get_job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager