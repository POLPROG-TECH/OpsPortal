"""Tests for configuration and manifest parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from opsportal.config.manifest import PortalManifest, ToolConfig, load_manifest
from opsportal.core.settings import PortalSettings


def test_settings_defaults() -> None:
    """GIVEN the settings defaults scenario."""

    """WHEN executing."""
    s = PortalSettings(manifest_path=Path("/tmp/test.yaml"))

    """THEN the result is correct."""
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.debug is False
    assert s.log_level == "info"


def test_settings_invalid_log_level() -> None:
    """GIVEN the settings invalid log level scenario."""

    """THEN the result is correct."""

    """WHEN executing."""
    with pytest.raises(ValueError, match="Invalid log level"):
        PortalSettings(log_level="verbose", manifest_path=Path("/tmp/test.yaml"))


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    """GIVEN the load manifest missing file scenario."""

    """WHEN executing."""
    m = load_manifest(tmp_path / "nope.yaml", tmp_path)

    """THEN the result is correct."""
    assert len(m.tools) == 0


def test_load_manifest_empty(tmp_path: Path) -> None:
    """GIVEN the load manifest empty scenario."""
    f = tmp_path / "m.yaml"
    f.write_text("tools: {}\n")

    """WHEN executing."""
    m = load_manifest(f, tmp_path)

    """THEN the result is correct."""
    assert len(m.tools) == 0


def test_load_manifest_with_tools(tmp_path: Path) -> None:
    """GIVEN the load manifest with tools scenario."""
    f = tmp_path / "m.yaml"
    tool_dir = tmp_path / "MyTool"
    tool_dir.mkdir()
    f.write_text(
        f"""
tools:
  mytool:
    display_name: MyTool
    description: A test tool
    repo_path: {tool_dir}
    integration_mode: cli_task
    icon: box
    color: "#123456"
"""
    )

    """WHEN executing."""
    m = load_manifest(f, tmp_path)

    """THEN the result is correct."""
    assert len(m.tools) == 1
    t = m.tools[0]
    assert t.slug == "mytool"
    assert t.display_name == "MyTool"
    assert t.integration_mode.value == "cli_task"


def test_manifest_get_tool() -> None:
    """GIVEN the manifest get tool scenario."""

    """WHEN executing."""
    m = PortalManifest(
        tools=[
            ToolConfig(
                slug="a", display_name="A", repo_path=Path("/tmp/a"), integration_mode="cli_task"
            ),
            ToolConfig(
                slug="b", display_name="B", repo_path=Path("/tmp/b"), integration_mode="hybrid"
            ),
        ]
    )

    """THEN the result is correct."""
    assert m.get_tool("a") is not None
    assert m.get_tool("a").display_name == "A"
    assert m.get_tool("c") is None


def test_manifest_enabled_tools() -> None:
    """GIVEN the manifest enabled tools scenario."""

    """WHEN executing."""
    m = PortalManifest(
        tools=[
            ToolConfig(
                slug="on",
                display_name="On",
                repo_path=Path("/tmp/on"),
                integration_mode="cli_task",
                enabled=True,
            ),
            ToolConfig(
                slug="off",
                display_name="Off",
                repo_path=Path("/tmp/off"),
                integration_mode="cli_task",
                enabled=False,
            ),
        ]
    )

    """THEN the result is correct."""
    assert len(m.enabled_tools) == 1
    assert m.enabled_tools[0].slug == "on"
