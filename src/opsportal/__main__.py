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


@app.command()
def version() -> None:
    """Show OpsPortal version."""
    typer.echo(f"OpsPortal v{__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
