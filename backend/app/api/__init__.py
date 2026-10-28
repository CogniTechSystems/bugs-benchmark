from fastapi import APIRouter

from app.api import bug_hunts, deployments, jobs, models, runtimes, sessions

api_router = APIRouter(prefix="/api")
for module in (models, runtimes, deployments, sessions, bug_hunts, jobs):
    api_router.include_router(module.router)
