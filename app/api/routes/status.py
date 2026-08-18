from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.deps import get_job_manager
from app.schemas.api import JobStatusResponse
from app.services.job_manager import JobManager

router = APIRouter()

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str, job_manager: JobManager = Depends(get_job_manager)):
    record = job_manager.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        plan=record.plan,
        task_plan=record.task_plan,
        error=record.error,
    )


@router.websocket("/ws/{job_id}")
async def job_progress_ws(
    websocket: WebSocket,
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
):
    if job_manager.get_job(job_id) is None:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    try:
        async for update in job_manager.subscribe(job_id):
            await websocket.send_json(update)
    except WebSocketDisconnect:
        pass