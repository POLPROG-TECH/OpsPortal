"""Tests for configuration and manifest parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from opsportal.config.manifest import PortalManifest, ToolConfig, load_manifest
from opsportal.core.settings import PortalSettings


def test_settings_defaults() -> None:
    """Default PortalSettings have expected host, port, and log level."""
    """GIVEN default settings."""
    s = PortalSettings(manifest_path=Path("/tmp/test.yaml"))

    """THEN all defaults are correct."""
    assert s.host == "127.0.0.1"
    assert s.port == 8000
    assert s.debug is False
    assert s.log_level == "info"


def test_settings_invalid_log_level() -> None:
    """PortalSettings rejects an unsupported log level with ValueError."""
    """WHEN creating settings with an invalid log level."""
    """THEN a ValueError is raised."""
    with pytest.raises(ValueError, match="Invalid log level"):
        PortalSettings(log_level="verbose", manifest_path=Path("/tmp/test.yaml"))


def test_load_manifest_missing_file(tmp_path: Path) -> None:
    """Loading a manifest from a non-existent file returns an empty tool list."""
    """WHEN loading a manifest from a missing file."""
    m = load_manifest(tmp_path / "nope.yaml", tmp_path)

    """THEN the manifest has no tools."""
    assert len(m.tools) == 0


def test_load_manifest_empty(tmp_path: Path) -> None:
    """Loading a manifest with an empty tools dict returns no tools."""
    """GIVEN a manifest file with an empty tools section."""
    f = tmp_path / "m.yaml"
    f.write_text("tools: {}\n")

    """WHEN loading the manifest."""
    m = load_manifest(f, tmp_path)

    """THEN the manifest has no tools."""
    assert len(m.tools) == 0


def test_load_manifest_with_tools(tmp_path: Path) -> None:
    """Loading a manifest with a tool entry populates slug, name, and mode."""
    """GIVEN a manifest file with one tool configured."""
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

    """WHEN loading the manifest."""
    m = load_manifest(f, tmp_path)

    """THEN the tool is parsed with correct attributes."""
    assert len(m.tools) == 1
    t = m.tools[0]
    assert t.slug == "mytool"
    assert t.display_name == "MyTool"
    assert t.integration_mode.value == "cli_task"


def test_manifest_get_tool() -> None:
    """PortalManifest.get_tool returns the matching tool or None."""
    """GIVEN a manifest with two tools."""
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

    """THEN known slugs return the tool and unknown slugs return None."""
    assert m.get_tool("a") is not None
    assert m.get_tool("a").display_name == "A"
    assert m.get_tool("c") is None


def test_manifest_enabled_tools() -> None:
    """PortalManifest.enabled_tools excludes disabled tools."""
    """GIVEN a manifest with one enabled and one disabled tool."""
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

    """THEN only the enabled tool is returned."""
    assert len(m.enabled_tools) == 1
    assert m.enabled_tools[0].slug == "on"
