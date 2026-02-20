"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(async_client: AsyncClient) -> None:
    """Test that health endpoint returns 200 status code."""
    # Arrange
    endpoint = "/api/v4/health"

    # Act
    response = await async_client.get(endpoint)

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()


@pytest.mark.asyncio
async def test_health_endpoint_returns_json(async_client: AsyncClient) -> None:
    """Test that health endpoint returns JSON content type."""
    # Act
    response = await async_client.get("/api/v4/health")

    # Assert
    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_health_endpoint_response_structure(async_client: AsyncClient) -> None:
    """Test that health endpoint returns correct response structure."""
    # Act
    response = await async_client.get("/api/v4/health")

    # Assert
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_endpoint_returns_message(async_client: AsyncClient) -> None:
    """Test that root endpoint returns a welcome message."""
    # Act
    response = await async_client.get("/")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "SIT Copilot" in data["message"]
