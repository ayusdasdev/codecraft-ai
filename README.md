# CodeCraft AI

CodeCraft AI is a FastAPI backend for turning a natural-language prompt into a project plan and generated code artifacts using a LangGraph + Groq-based workflow.

It supports:

- Planning a project from a user prompt
- Starting asynchronous generation jobs
- Monitoring job status via REST and WebSocket endpoints
- Uploading generated project output to S3 (optional)

## Features

- REST API built with FastAPI
- Structured planning using Groq-hosted LLMs
- Background job orchestration with async task tracking
- WebSocket streaming for generation progress
- Optional S3 artifact storage for generated projects

## Project structure

```text
app/
├── api/
│   ├── deps.py
│   └── routes/
│       ├── artifacts.py
│       ├── generate.py
│       ├── plan.py
│       └── status.py
├── core/
│   ├── config.py
│   └── logging.py
├── schemas/
│   ├── agent.py
│   ├── api.py
│   └── __init__.py
├── services/
│   ├── agent_graph.py
│   ├── agent_tools.py
│   ├── job_manager.py
│   └── storage.py
├── main.py
└── __init__.py
```

## Tech stack

- Python 3.12
- FastAPI
- LangChain / LangGraph
- Groq API
- Pydantic + BaseSettings
- Boto3 for S3 support
- Docker Compose for containerized deployment

## Prerequisites

- Python 3.12+
- Pip
- Optional: Docker and Docker Compose
- Groq API key

## Environment variables

Create a `.env` file or configure environment variables before starting the app.

```bash
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
CORS_ORIGINS=http://localhost:3000
AWS_REGION=us-east-1
CONFIG_S3_BUCKET=your-s3-bucket
CONFIG_S3_KEY=config/.aws_credentials
S3_ARTIFACTS_BUCKET=your-artifacts-bucket
```

Notes:

- `GROQ_API_KEY` can also be passed per request in the API body.
- `CONFIG_S3_BUCKET`/`CONFIG_S3_KEY` are used to load additional AWS credentials from S3 before app startup.
- Artifact upload to S3 is optional and only happens when the bucket is configured.

## Local setup

1. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or .venv\Scripts\activate  # Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Health check:

```bash
curl http://localhost:8000/health
```

## API usage

### 1. Create a project plan

```bash
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Build a simple Python FastAPI service for todo management",
    "groq_api_key": "your_groq_api_key"
  }'
```

### 2. Start async generation

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a React + FastAPI starter app with authentication",
    "groq_api_key": "your_groq_api_key"
  }'
```

Response:

```json
{
  "job_id": "<uuid>",
  "status": "pending"
}
```

### 3. Check job status

```bash
curl http://localhost:8000/api/status/<job_id>
```

### 4. Watch progress via WebSocket

```text
ws://localhost:8000/api/ws/<job_id>
```

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

The service is exposed on port `8000`.

## Endpoints

- `GET /health` - Liveness check
- `POST /api/plan` - Generate a structured plan from a prompt
- `POST /api/generate` - Start background generation job
- `GET /api/status/{job_id}` - Fetch job status
- `WS /api/ws/{job_id}` - Real-time progress updates
- `GET /api/artifacts/{job_id}` - Retrieve generation artifacts, if configured

## Notes

This repository is the backend service for a prompt-to-code workflow. In practice, the generated project files are produced in a temporary workspace and may be uploaded to S3 for later retrieval or download.

## License

This project does not currently declare a license.
