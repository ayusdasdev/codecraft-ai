import pathlib
import shutil
import boto3


def get_s3_client(region: str):
    return boto3.client("s3", region_name=region)


def upload_directory_to_s3(client, project_root: pathlib.Path, bucket: str, prefix: str) -> list[str]:
    """Upload every file under project_root to S3, preserving relative paths. Returns the keys."""
    keys = []
    for file_path in project_root.rglob("*"):
        if file_path.is_file():
            relative = file_path.relative_to(project_root)
            key = f"{prefix}/{relative.as_posix()}"
            client.upload_file(str(file_path), bucket, key)
            keys.append(key)
    return keys


def upload_zip_of_directory(client, project_root: pathlib.Path, bucket: str, prefix: str) -> str:
    """Zip the whole project and upload it as one object. Returns the zip's key."""
    archive_base = str(project_root) + "_archive"
    zip_path = shutil.make_archive(archive_base, "zip", root_dir=project_root)
    key = f"{prefix}/project.zip"
    client.upload_file(zip_path, bucket, key)
    pathlib.Path(zip_path).unlink(missing_ok=True)
    return key


def generate_presigned_url(client, bucket: str, key: str, expires_in: int = 3600) -> str:
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )