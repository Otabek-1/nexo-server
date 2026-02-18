import boto3
from botocore.config import Config

from app.core.config import get_settings
from app.integrations.storage.base import SignedUpload, StorageProvider


class S3StorageProvider(StorageProvider):
    name = "s3"

    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = settings.s3_bucket

    def sign_upload(self, object_key: str, mime_type: str, size_bytes: int) -> SignedUpload:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": mime_type,
            },
            ExpiresIn=self.settings.storage_sign_ttl_seconds,
            HttpMethod="PUT",
        )
        public_base = self.settings.s3_public_base_url.rstrip("/")
        public_url = f"{public_base}/{object_key}" if public_base else f"{url.split('?')[0]}"
        return SignedUpload(
            upload_url=url,
            method="PUT",
            headers={"Content-Type": mime_type},
            public_url=public_url,
            object_key=object_key,
            bucket=self.bucket,
        )

