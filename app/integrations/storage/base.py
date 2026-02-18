from dataclasses import dataclass


@dataclass
class SignedUpload:
    upload_url: str
    method: str
    headers: dict[str, str]
    public_url: str
    object_key: str
    bucket: str


class StorageProvider:
    name: str = "base"

    def sign_upload(self, object_key: str, mime_type: str, size_bytes: int) -> SignedUpload:
        raise NotImplementedError

