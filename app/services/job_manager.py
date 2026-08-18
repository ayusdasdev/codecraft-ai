import asyncio
import pathlib
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional
from app.services.storage import get_s3_client, upload_directory_to_s3, upload_zip_of_directory

from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.agent import Plan, TaskPlan
from app.schemas.api import JobStatus
from app.services.agent_graph import create_llm, build_graph, run_agent_streaming
from app.services.agent_tools import make_tools_for_job

MAX_JOBS = 500

STATUS_BY_NODE = {
    "planner": JobStatus.PLANNING,
    "architect": JobStatus.ARCHITECTING,
    "coder": JobStatus.CODING,
}


class JobRecord:
    def __init__(self, job_id: str, prompt: str):
        self.job_id = job_id
        self.prompt = prompt
        self.status = JobStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.plan: Optional[Plan] = None
        self.task_plan: Optional[TaskPlan] = None
        self.current_step_idx = 0
        self.error: Optional[str] = None
        self.subscribers: list[asyncio.Queue] = []
        self.s3_bucket: Optional[str] = None
        self.s3_prefix: Optional[str] = None
        self.s3_zip_key: Optional[str] = None
        self.s3_file_keys: list[str] = []


class JobManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    async def create_job(self, prompt: str, groq_api_key: Optional[SecretStr]) -> JobRecord:
        job_id = str(uuid.uuid4())
        record = JobRecord(job_id=job_id, prompt=prompt)
        async with self._lock:
            if len(self._jobs) >= MAX_JOBS:
                oldest_id = min(self._jobs, key=lambda jid: self._jobs[jid].created_at)
                del self._jobs[oldest_id]
            self._jobs[job_id] = record

        api_key = groq_api_key or self._settings.groq_api_key
        task = asyncio.create_task(self._run_job(record, api_key))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    async def subscribe(self, job_id: str):
        record = self._jobs.get(job_id)
        if record is None:
            return

        queue: asyncio.Queue = asyncio.Queue()
        record.subscribers.append(queue)
        try:
            while True:
                update = await queue.get()
                yield update
                if update["status"] in (JobStatus.DONE, JobStatus.FAILED):
                    break
        finally:
            record.subscribers.remove(queue)

    async def _emit(self, record: JobRecord, status: JobStatus, message: str) -> None:
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        for queue in list(record.subscribers):
            await queue.put({"job_id": record.job_id, "status": status, "message": message})

    async def _run_job(self, record: JobRecord, api_key: SecretStr) -> None:
        await self._emit(record, JobStatus.PENDING, "Job accepted, starting pipeline")

        project_root = pathlib.Path(tempfile.mkdtemp(prefix=f"ai_coder_{record.job_id}_"))
        loop = asyncio.get_running_loop()

        def on_event(node_name: str, state: dict) -> None:
            status = STATUS_BY_NODE.get(node_name, record.status)
            asyncio.run_coroutine_threadsafe(
                self._emit(record, status, f"{node_name} completed"),
                loop,
            )

        try:
            tools_dict = make_tools_for_job(project_root)
            tools = list(tools_dict.values())
            llm = create_llm(api_key, self._settings.groq_model)
            graph = build_graph(llm, tools, project_root)

            final_state = await asyncio.to_thread(
                run_agent_streaming, graph, record.prompt, on_event
            )
            record.plan = final_state["plan"]
            record.task_plan = final_state["task_plan"]
            if self._settings.s3_artifacts_bucket:
                await self._emit(record, JobStatus.CODING, "Uploading generated project to S3")
                client = get_s3_client(self._settings.aws_region)
                prefix = f"{self._settings.s3_artifacts_prefix}/{record.job_id}"
                file_keys, zip_key = await asyncio.to_thread(
                    self._upload_all, client, project_root, self._settings.s3_artifacts_bucket, prefix
                )
                record.s3_bucket = self._settings.s3_artifacts_bucket
                record.s3_prefix = prefix
                record.s3_zip_key = zip_key
                record.s3_file_keys = file_keys
            await self._emit(record, JobStatus.DONE, "Generation complete")

        except Exception as exc:
            record.error = str(exc)
            await self._emit(record, JobStatus.FAILED, f"Job failed: {exc}")
        finally:
            shutil.rmtree(project_root, ignore_errors=True)

    @staticmethod
    def _upload_all(client, project_root, bucket, prefix):
        file_keys = upload_directory_to_s3(client, project_root, bucket, prefix)
        zip_key = upload_zip_of_directory(client, project_root, bucket, prefix)
        return file_keys, zip_key

    async def shutdown(self, timeout: float = 30.0) -> None:
        if not self._tasks:
            return

        pending = set(self._tasks)
        done, still_pending = await asyncio.wait(pending, timeout=timeout)

        if still_pending:
            for task in still_pending:
                task.cancel()
            await asyncio.gather(*still_pending, return_exceptions=True)