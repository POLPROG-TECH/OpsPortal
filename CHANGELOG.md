# Changelog

All notable changes to **OpsPortal** will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.1.0] — 2026-03-29

### Added

- **FlowBoard adapter** — delivery intelligence dashboards from Jira data
- **AppSecOne adapter** — security posture dashboard powered by Fortify SSC
- Both tools registered in manifest (`opsportal.yaml`), factory, and default configuration
- 18 new tests covering adapter identity, capabilities, lifecycle, and framing env vars (256 total)

## [1.0.0] — 2026-03-28

### Added

- **Web dashboard** — unified operations portal with tool embedding via iframes, live status indicators, version badges, and capability tags
- **CLI** — `serve`, `init`, `setup`, `version` commands via Typer
- **Tool orchestration** — automatic installation from remote Git sources, subprocess process management, health monitoring via `/health/live`
- **Configuration** — YAML-based manifest (`opsportal.yaml`) with environment variable overrides and multi-strategy config file resolution
- **Adapters** — ReleaseBoard, ReleasePilot, LocaleSync integration with JSON Schema-based config UI (save, validate, restart)
- **Security** — CSRF protection, Content-Security-Policy headers with dynamic `frame-src`, `X-Frame-Options`, request sanitization
- **Iframe embedding** — fallback UI for blocked embeds, width expansion controls (left/right/reset), shimmer loading skeleton
- **i18n** — English and Polish translations
- **238 tests** — unit, integration, security, UI regression
- **Docker** support with multi-stage build
- **CI/CD** pipeline configuration for GitHub Actions and GitLab CI
- **Corporate proxy / SSL** support with automatic environment variable forwarding to child processes
- **Remote tool sourcing** — managed installation model with `pip_git`, `pip_registry`, and `pre_installed` strategies
