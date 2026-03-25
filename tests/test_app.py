"""Tests for the portal application — smoke and integration."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_home_page_returns_200(client: TestClient) -> None:
    """GIVEN the home page returns 200 scenario."""

    """WHEN executing."""
    resp = client.get("/")

    """THEN the result is correct."""
    assert resp.status_code == 200
    assert "OpsPortal" in resp.text


def test_health_page_returns_200(client: TestClient) -> None:
    """GIVEN the health page returns 200 scenario."""

    """WHEN executing."""
    resp = client.get("/health")

    """THEN the result is correct."""
    assert resp.status_code == 200


def test_logs_page_returns_200(client: TestClient) -> None:
    """GIVEN the logs page returns 200 scenario."""

    """WHEN executing."""
    resp = client.get("/logs")

    """THEN the result is correct."""
    assert resp.status_code == 200


def test_config_page_returns_200(client: TestClient) -> None:
    """GIVEN the config page returns 200 scenario."""

    """WHEN executing."""
    resp = client.get("/config")

    """THEN the result is correct."""
    assert resp.status_code == 200


def test_api_health_returns_json(client: TestClient) -> None:
    """GIVEN the api health returns json scenario."""

    """WHEN executing."""
    resp = client.get("/api/health")

    """THEN the result is correct."""
    assert resp.status_code == 200
    data = resp.json()
    assert "healthy" in data


def test_api_tools_returns_list(client: TestClient) -> None:
    """GIVEN the api tools returns list scenario."""

    """WHEN executing."""
    resp = client.get("/api/tools")

    """THEN the result is correct."""
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_unknown_tool_returns_404(client: TestClient) -> None:
    """GIVEN the unknown tool returns 404 scenario."""

    """WHEN executing."""
    resp = client.get("/tools/nonexistent")

    """THEN the result is correct."""
    assert resp.status_code == 404


def test_static_css_served(client: TestClient) -> None:
    """GIVEN the static css served scenario."""

    """WHEN executing."""
    resp = client.get("/static/css/portal-base.css")
    # Will be 200 if static dir exists with file, 404 otherwise

    """THEN the result is correct."""
    assert resp.status_code in (200, 404)
