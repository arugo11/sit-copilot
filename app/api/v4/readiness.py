"""Readiness check API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.auth import require_lecture_token
from app.schemas.readiness import ReadinessCheckRequest, ReadinessCheckResponse
from app.services.readiness_service import (
    DeterministicReadinessService,
    ReadinessService,
)

router = APIRouter(
    prefix="/course/readiness",
    tags=["readiness"],
    dependencies=[Depends(require_lecture_token)],
)


def get_readiness_service() -> ReadinessService:
    """Dependency provider for readiness check service."""
    return DeterministicReadinessService()


@router.post(
    "/check",
    status_code=status.HTTP_200_OK,
    response_model=ReadinessCheckResponse,
)
async def check_course_readiness(
    request: ReadinessCheckRequest,
    service: Annotated[ReadinessService, Depends(get_readiness_service)],
) -> ReadinessCheckResponse:
    """Return deterministic readiness guidance from course inputs."""
    return await service.check(request)
