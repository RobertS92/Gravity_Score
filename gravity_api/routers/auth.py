"""Auth stubs — JWT + roles in Week 2."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def auth_health():
    return {"auth": "stub", "detail": "Implement JWT in routers/auth.py"}
