"""Health check API endpoints."""

from fastapi import APIRouter, status

from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
)
async def get_health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")
