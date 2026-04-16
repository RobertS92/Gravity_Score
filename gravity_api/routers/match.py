"""Brand–athlete match / compatibility."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gravity_api.services.compatibility import compatibility_score

router = APIRouter()


class CompatibilityBody(BaseModel):
    athlete: dict[str, Any] = Field(default_factory=dict)
    brand: dict[str, Any] = Field(default_factory=dict)
    brief: dict[str, Any] = Field(default_factory=dict)


@router.post("/compatibility")
async def post_compatibility(body: CompatibilityBody):
    return compatibility_score(body.athlete, body.brand, body.brief or None)
