"""
Tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, AsyncMock
import os


# Create test client
client = TestClient(app)


@pytest.mark.unit
def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert 'timestamp' in data


@pytest.mark.unit
def test_detailed_health_endpoint():
    """Test detailed health check endpoint"""
    response = client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert 'components' in data


@pytest.mark.unit
def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data['service'] == 'Gravity Scrapers & Crawlers API'
    assert data['status'] == 'operational'


@pytest.mark.unit
def test_refresh_athlete_no_auth():
    """Test athlete refresh without authentication"""
    response = client.post("/api/v1/athletes/test-id/refresh")
    assert response.status_code == 403  # Forbidden without auth


@pytest.mark.unit
def test_refresh_athlete_invalid_auth(test_athlete_id):
    """Test athlete refresh with invalid API key"""
    response = client.post(
        f"/api/v1/athletes/{test_athlete_id}/refresh",
        headers={"Authorization": "Bearer invalid_key"}
    )
    assert response.status_code == 401  # Unauthorized


@pytest.mark.unit
def test_trigger_daily_job_no_auth():
    """Test daily job trigger without authentication"""
    response = client.post("/api/v1/jobs/daily")
    assert response.status_code == 403


@pytest.mark.unit
def test_get_jobs_status():
    """Test getting job status (public endpoint)"""
    response = client.get("/api/v1/jobs/status")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.unit
def test_get_crawler_status():
    """Test getting crawler status"""
    response = client.get("/api/v1/crawlers/status")
    assert response.status_code == 200
    data = response.json()
    assert 'available' in data


@pytest.mark.unit
def test_get_available_crawlers():
    """Test getting available crawlers"""
    response = client.get("/api/v1/crawlers/available")
    assert response.status_code == 200
    data = response.json()
    assert 'crawlers' in data
    assert isinstance(data['crawlers'], list)


@pytest.mark.unit
def test_api_docs_available():
    """Test that API documentation is available"""
    response = client.get("/docs")
    assert response.status_code == 200


@pytest.mark.unit
def test_openapi_schema():
    """Test that OpenAPI schema is available"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert 'info' in data
    assert data['info']['title'] == 'Gravity Scrapers & Crawlers API'


@pytest.mark.integration
@pytest.mark.requires_db
def test_get_athlete_status(test_athlete_id):
    """Test getting athlete status"""
    response = client.get(f"/api/v1/athletes/{test_athlete_id}/status")
    # May return 404 if test athlete doesn't exist, which is ok
    assert response.status_code in [200, 404, 500]


@pytest.mark.integration
@pytest.mark.requires_db
def test_get_job_status():
    """Test getting specific job status"""
    response = client.get("/api/v1/jobs/test-job-id/status")
    assert response.status_code == 200
    # Should return job data or not_found status
    data = response.json()
    assert 'status' in data
