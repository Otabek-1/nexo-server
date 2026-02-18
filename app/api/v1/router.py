from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, plans, storage, subscriptions, tests, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(plans.router)
api_router.include_router(subscriptions.router)
api_router.include_router(tests.router)
api_router.include_router(storage.router)
api_router.include_router(health.router)

