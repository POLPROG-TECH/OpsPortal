"""Entry point for ``python -m opsportal`` and the ``opsportal`` CLI command."""

from __future__ import annotations

from pathlib import Path

import typer

from opsportal import __version__

app = typer.Typer(
    name="opsportal",
    help="OpsPortal — Unified operations portal for internal developer tools",
    no_args_is_help=True,
)


def _ensure_manifest(manifest_path: Path) -> None:
    """Generate default opsportal.yaml if missing (auto-bootstrap)."""
    if manifest_path.exists():
        return

    from opsportal.config.manifest import DEFAULT_MANIFEST_YAML

    manifest_path.write_text(DEFAULT_MANIFEST_YAML, encoding="utf-8")
    typer.echo(f"✔ Generated default manifest: {manifest_path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int | None = typer.Option(None, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Start the OpsPortal web server."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("Error: uvicorn is required. Install with: pip install opsportal", err=True)
        raise typer.Exit(1) from None

    from opsportal.core.settings import get_settings

    settings = get_settings()
    _ensure_manifest(settings.manifest_path)

    port = port or settings.port
    log_level = "debug" if verbose else settings.log_level

    uvicorn.run(
        "opsportal.app.factory:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload or settings.debug,
        log_level=log_level,
    )


_DEFAULT_INIT_PATH = typer.Argument(
    Path("opsportal.yaml"),
    help="Path where manifest file will be created",
)


@app.command()
def init(
    path: Path = _DEFAULT_INIT_PATH,
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file"),
) -> None:
    """Generate a default opsportal.yaml manifest."""
    from opsportal.config.manifest import DEFAULT_MANIFEST_YAML

    if path.exists() and not force:
        typer.echo(f"✗ File already exists: {path}  (use --force to overwrite)", err=True)
        raise typer.Exit(1)

    path.write_text(DEFAULT_MANIFEST_YAML, encoding="utf-8")
    typer.echo(f"✔ Created {path}")
    typer.echo("  Edit the file to customize tools, then run: opsportal serve")


_DEFAULT_SETUP_MANIFEST = typer.Option(
    Path("opsportal.yaml"), "--manifest", "-m", help="Path to manifest file"
)


@app.command()
def setup(
    manifest: Path = _DEFAULT_SETUP_MANIFEST,
) -> None:
    """Set up OpsPortal: create manifest, install tools, and scaffold configs.

    This is the recommended first-run command after installing OpsPortal.
    It creates the manifest file if missing, installs declared tools from
    their remote sources, and scaffolds default configuration files.
    """
    from opsportal.config.manifest import DEFAULT_MANIFEST_YAML, load_manifest
    from opsportal.services.tool_installer import ToolInstaller

    # Step 1: Ensure manifest exists
    if not manifest.exists():
        manifest.write_text(DEFAULT_MANIFEST_YAML, encoding="utf-8")
        typer.echo(f"✔ Created manifest: {manifest}")
    else:
        typer.echo(f"✔ Manifest found: {manifest}")

    # Step 2: Load manifest and install tools
    work_dir = Path("work/tools")
    work_dir.mkdir(parents=True, exist_ok=True)
    portal_manifest = load_manifest(manifest, Path("."), tools_work_dir=work_dir)

    if not portal_manifest.enabled_tools:
        typer.echo("  No tools registered in manifest.")
        typer.echo("  Edit opsportal.yaml and re-run: opsportal setup")
        return

    installer = ToolInstaller(work_dir)
    for tool in portal_manifest.enabled_tools:
        typer.echo(f"\n── {tool.display_name} ({tool.slug}) ──")

        # Install from source if defined
        if tool.source:
            typer.echo(f"  Installing from {tool.source.repository}@{tool.source.ref}...")
            try:
                result = installer.ensure_installed(tool.source)
                ver = result.get("version", "?")
                typer.echo(f"  ✔ {result['action']}: {result['package']} v{ver}")
            except Exception as exc:
                typer.echo(f"  ✗ Install failed: {exc}", err=True)
                continue

        # Scaffold config if adapter supports it
        tool_work = installer.work_dir_for(tool.slug)
        _scaffold_tool_config(tool.slug, tool, tool_work)

    typer.echo("\n✔ Setup complete. Start the portal with: opsportal serve")


def _scaffold_tool_config(slug: str, tool, work_dir: Path) -> None:
    """Attempt to scaffold default config for a tool."""
    from opsportal.services.process_manager import ProcessManager

    pm = ProcessManager()
    adapter = _create_adapter_for_scaffold(slug, tool, work_dir, pm)

    if adapter is None:
        return

    if adapter.config_file_path() is not None:
        typer.echo(f"  ✔ Config already exists: {adapter._config_file}")
        return

    if adapter.scaffold_default_config():
        typer.echo(f"  ✔ Scaffolded default config: {adapter._config_file}")
        return

    config_path = adapter._resolve_config_path()
    typer.echo(
        f"  ⚠ Could not auto-scaffold config (no schema with defaults found).\n"
        f"    Create config manually at: {config_path}\n"
        f"    Or use the web UI Configuration page after starting the portal."
    )


def _create_adapter_for_scaffold(slug: str, tool, work_dir: Path, pm):
    """Create the appropriate adapter instance for config scaffolding."""
    if slug == "releasepilot":
        from opsportal.adapters.releasepilot import ReleasePilotAdapter

        return ReleasePilotAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8082,
        )

    if slug == "releaseboard":
        from opsportal.adapters.releaseboard import ReleaseBoardAdapter

        return ReleaseBoardAdapter(
            pm,
            repo_path=tool.repo_path,
            work_dir=work_dir,
            port=tool.port or 8081,
            config_file=tool.config_file or "releaseboard.json",
        )

    return None


@app.command()
def version() -> None:
    """Show OpsPortal version."""
    typer.echo(f"OpsPortal v{__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
