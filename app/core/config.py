import io
import os
from functools import lru_cache
from typing import Annotated

import boto3
from dotenv import dotenv_values, load_dotenv
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, NoDecode

load_dotenv()

def load_env_from_s3(bucket: str, key: str, region: str) -> None:
    """Fetch an .aws_credentials-shaped file from S3 and inject it into os.environ, before Settings() is built."""
    client = boto3.client("s3", region_name=region)
    response = client.get_object(Bucket=bucket, Key=key)
    raw_text = response["Body"].read().decode("utf-8")

    values = dotenv_values(stream=io.StringIO(raw_text))
    for k, v in values.items():
        if v is not None:
            os.environ.setdefault(k, v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".aws_credentials", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CodeCraft AI Backend"
    log_level: str = "INFO"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    cors_origins: Annotated[list[str], NoDecode] = Field(default=["http://localhost:3000"])
    s3_artifacts_bucket: str = ""
    s3_artifacts_prefix: str = "jobs"
    aws_region: str = "us-east-1"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    s3_config_bucket = os.environ.get("CONFIG_S3_BUCKET")
    print(f"DEBUG: CONFIG_S3_BUCKET = {s3_config_bucket!r}")
    if s3_config_bucket:
        try:
            load_env_from_s3(
                bucket=s3_config_bucket,
                key=os.environ.get("CONFIG_S3_KEY", ".aws_credentials"),
                region=os.environ.get("AWS_REGION", "us-east-1"),
            )
        except Exception as exc:
            print(f"DEBUG: S3 config load FAILED: {exc}")

    return Settings()