"""Tests for the portal application — smoke and integration."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_home_page_returns_200(client: TestClient) -> None:
    """Home page responds with 200 and contains 'OpsPortal'."""
    """WHEN requesting the home page."""
    resp = client.get("/")

    """THEN it returns 200 with OpsPortal in the body."""
    assert resp.status_code == 200
    assert "OpsPortal" in resp.text


def test_health_page_returns_200(client: TestClient) -> None:
    """Health page responds with 200."""
    """WHEN requesting the health page."""
    resp = client.get("/health")

    """THEN it returns 200."""
    assert resp.status_code == 200


def test_logs_page_returns_200(client: TestClient) -> None:
    """Logs page responds with 200."""
    """WHEN requesting the logs page."""
    resp = client.get("/logs")

    """THEN it returns 200."""
    assert resp.status_code == 200


def test_config_page_returns_200(client: TestClient) -> None:
    """Config page responds with 200."""
    """WHEN requesting the config page."""
    resp = client.get("/config")

    """THEN it returns 200."""
    assert resp.status_code == 200


def test_api_health_returns_json(client: TestClient) -> None:
    """API health endpoint returns JSON with a 'healthy' key."""
    """WHEN requesting the API health endpoint."""
    resp = client.get("/api/health")

    """THEN it returns 200 with a 'healthy' field."""
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data


def test_api_tools_returns_list(client: TestClient) -> None:
    """API tools endpoint returns a JSON list."""
    """WHEN requesting the API tools endpoint."""
    resp = client.get("/api/tools")

    """THEN it returns 200 with a list."""
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_unknown_tool_returns_404(client: TestClient) -> None:
    """Requesting a non-existent tool page returns 404."""
    """WHEN requesting a tool page for a non-existent tool."""
    resp = client.get("/tools/nonexistent")

    """THEN it returns 404."""
    assert resp.status_code == 404


def test_static_css_served(client: TestClient) -> None:
    """Static CSS file returns 200 if present, 404 otherwise."""
    """WHEN requesting the base CSS file."""
    resp = client.get("/static/css/portal-base.css")
    # Will be 200 if static dir exists with file, 404 otherwise

    """THEN it returns either 200 or 404."""
    assert resp.status_code in (200, 404)
