from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

PRODUCTION_CORS_ORIGINS = {"https://nexoo.space", "https://www.nexoo.space"}


def with_cors(app: ASGIApp, configured_origins: str) -> ASGIApp:
    origins = {
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    }
    origins.update(PRODUCTION_CORS_ORIGINS)
    return CORSMiddleware(
        app,
        allow_origins=sorted(origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
