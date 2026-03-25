<p align="center">
  <img alt="OpsPortal" src="docs/assets/logo-full.svg" width="420">
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <img src="https://img.shields.io/badge/tests-172%20passed-22c55e?style=flat-square&logo=pytest&logoColor=white" alt="Tests: 172 passed">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-6366f1?style=flat-square" alt="License: AGPL-3.0"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
</p>

<p align="center">
  <b>Unified developer operations platform for internal tools.</b><br>
  <sub>Tool orchestration · Iframe embedding · Health monitoring · Config management · Auto-install from remote sources</sub>
</p>

<p align="center">
  <a href="#what-is-opsportal">About</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#cicd-pipelines">CI/CD</a> •
  <a href="#troubleshooting">Troubleshooting</a> •
  <a href="#development">Development</a>
</p>

---

## What is OpsPortal?

OpsPortal is the orchestrator and entry point for a family of FastAPI web applications
that share the same architectural model. It provides a unified dashboard to launch,
monitor, and manage internal engineering tools.

| Tool | Port | Purpose |
|------|------|---------|
| **ReleasePilot** | 8082 | Release notes generation from git history |
| **ReleaseBoard** | 8081 | Release readiness dashboard across repos |

Every tool is a full web application — OpsPortal starts each on demand, monitors health,
and embeds them in the portal UI via iframe with automatic theme and language forwarding.

## Table of Contents

- [What is OpsPortal?](#what-is-opsportal)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Portal Endpoints](#portal-endpoints)
- [Configuration](#configuration)
- [Registering Applications](#registering-applications)
- [ReleaseBoard Integration](#releaseboard-integration)
- [Application Embedding](#application-embedding)
- [Iframe Width Controls](#iframe-width-controls)
- [How Tool Auto-Start Works](#how-tool-auto-start-works)
- [Corporate Proxy / SSL](#corporate-proxy--ssl)
- [CSP Considerations](#csp-considerations)
- [CI/CD Pipelines](#cicd-pipelines)
- [Troubleshooting](#troubleshooting)
- [Unified Platform Architecture](#unified-platform-architecture)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

## Quick Start

### One command (fully remote)

```bash
pip install "git+https://github.com/POLPROG-TECH/OpsPortal.git@main" && opsportal serve
# → http://127.0.0.1:8000
```

That's it. On first run `opsportal serve` auto-generates `opsportal.yaml`
(with ReleaseBoard + ReleasePilot) and auto-installs both tools from GitHub.

### Step-by-step production deployment

```bash
# 1. Install OpsPortal
pip install "git+https://github.com/POLPROG-TECH/OpsPortal.git@main"

# 2. Generate the default manifest (optional — created automatically on serve)
opsportal init              # creates opsportal.yaml in current directory
# Edit to pin versions, change ports, add proxy env, etc.

# 3. Start the portal
opsportal serve
```

### Local development setup

```bash
# Clone all repos into a shared parent directory
mkdir opsportal-dev && cd opsportal-dev
git clone https://github.com/POLPROG-TECH/OpsPortal.git
git clone https://github.com/POLPROG-TECH/ReleasePilot.git
git clone https://github.com/POLPROG-TECH/ReleaseBoard.git

# Install everything in editable mode (quotes required for zsh)
pip3 install -e "./ReleasePilot[all]"
pip3 install -e ./ReleaseBoard
pip3 install -e ./OpsPortal

# Start from the OpsPortal directory
cd OpsPortal
opsportal serve
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    OpsPortal :9000 (FastAPI)                  │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐                           │
│  │ ReleasePilot │ │ ReleaseBoard │                           │
│  │   Adapter    │ │   Adapter    │                           │
│  └──────┬───────┘ └──────┬───────┘                           │
│         │                │                                    │
│    ProcessManager ───── ensure_running() + health poll       │
└─────────┼────────────────┼────────────────────────────────────┘
          │                │
    :8082 ▼          :8081 ▼
   ReleasePilot    ReleaseBoard
   (FastAPI)       (FastAPI)
```

Every tool follows the same pattern:
- **SUBPROCESS_WEB** integration — OpsPortal launches `{tool} serve --port N`
- **Health check** via `GET /health/live` → `{"status": "alive"}`
- **Iframe embedding** — each tool sets `{TOOL}_ALLOW_FRAMING=true`
- **On-demand lifecycle** — started when user clicks, stopped at portal shutdown

## Portal Endpoints

OpsPortal provides both HTML pages and a JSON API:

**Pages** — dashboard with tool tiles (`/`), per-tool context pages (`/tools/{slug}`), health overview, activity logs, and configuration viewer.

**API** — JSON endpoints for tool health (`/api/health`), tool listing (`/api/tools`), individual tool status, and lifecycle control (start/stop/restart).

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPSPORTAL_HOST` | `127.0.0.1` | Bind address |
| `OPSPORTAL_PORT` | `8000` | Bind port |
| `OPSPORTAL_DEBUG` | `false` | Debug mode |
| `OPSPORTAL_LOG_LEVEL` | `info` | Log level |
| `OPSPORTAL_MANIFEST_PATH` | `opsportal.yaml` | Tool manifest |
| `OPSPORTAL_ARTIFACT_DIR` | `artifacts` | Artifact storage |
| `OPSPORTAL_TOOLS_WORK_DIR` | `work/tools` | Per-tool work directories (configs, data) |
| `OPSPORTAL_TOOLS_BASE_DIR` | `..` | Legacy: parent directory for local repo paths |

### Tool Manifest (`opsportal.yaml`)

Tools can be sourced from **remote Git repositories** (production) or **local paths** (development):

```yaml
tools:
  releaseboard:
    display_name: ReleaseBoard
    integration_mode: subprocess_web
    port: 8081
    config_file: releaseboard.json
    source:
      provider: github
      repository: POLPROG-TECH/ReleaseBoard
      ref: v1.1.0
      package: releaseboard
      install_strategy: pip_git
    # Optional: local dev override
    # repo_path: ../ReleaseBoard

  releasepilot:
    display_name: ReleasePilot
    integration_mode: subprocess_web
    port: 8082
    source:
      provider: github
      repository: POLPROG-TECH/ReleasePilot
      ref: v1.1.0
      package: releasepilot
      extras: [all]
      install_strategy: pip_git
```

### CLI

```
opsportal serve [OPTIONS]     Start the portal server
  --host TEXT                 Bind host [default: 127.0.0.1]
  --port / -p INTEGER         Bind port [default: 9000]
  --reload                    Auto-reload for development
  --verbose / -v              Debug logging

opsportal version             Show version
```

## Registering Applications

Each tool is defined in the manifest file (`opsportal.yaml`). Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `display_name` | yes | Human-readable name shown on the dashboard card |
| `integration_mode` | yes | Must be `subprocess_web` (launches a child process with a web UI) |
| `port` | yes | Port the tool listens on when started |
| `source` | no¹ | Remote source definition (see below) |
| `repo_path` | no¹ | Local checkout path (relative to `OPSPORTAL_TOOLS_BASE_DIR`) |
| `config_file` | no | Config file name (resolved via multi-strategy lookup) |
| `startup_timeout` | no | Max seconds to wait for health check (default: 30) |
| `icon` | no | Icon identifier for the dashboard card |
| `color` | no | Hex color for the card accent (e.g., `#059669`) |
| `env` | no | Extra environment variables passed to the child process |

¹ At least one of `source` or `repo_path` should be defined.

### Remote tool source definition

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | no | `github` (default) or `gitlab` |
| `repository` | yes | `owner/name` format (e.g., `POLPROG-TECH/ReleasePilot`) |
| `ref` | no | Git tag, branch, or commit (default: `main`) |
| `package` | yes | Python package name (e.g., `releasepilot`) |
| `extras` | no | pip extras to install (e.g., `[all]`) |
| `install_strategy` | no | `pip_git` (default), `pip_registry`, or `pre_installed` |

When a tool has a `source` block and its CLI is not found on `$PATH`, OpsPortal
auto-installs it via `pip install git+https://github.com/owner/repo.git@ref[extras]`.

## Tool Configuration

Each configurable tool has a dedicated configuration page at `/tools/{slug}/config`.
The form is generated dynamically from the tool's JSON Schema.

### How config changes are applied

Config changes are saved to the tool's config file (e.g., `.releasepilot.json`,
`releaseboard.json`). **Tools load config at startup**, so a restart is required
for changes to take effect.

The config page provides two save options:
- **Save** — writes the file and shows a "restart required" banner with a Restart Now button
- **Save & Restart** — writes the file and immediately restarts the tool process

**Config loading chain:**
1. OpsPortal saves config to the tool's config file (atomic write)
2. On restart, OpsPortal stops the tool process and starts it again
3. The tool's `serve` command reads the config file as base defaults
4. CLI arguments (port, host) override file config values
5. The web server's `AppState.config` reflects the merged configuration

> **Note:** ReleasePilot's `serve` command loads `.releasepilot.json` automatically
> from the repository directory. ReleaseBoard receives its config path via `--config`.

### Schema-based validation

All config fields are validated against the tool's JSON Schema before save. Validation
is enforced server-side by the `JsonSchemaConfigMixin`:
1. Tool-specific validators (e.g., `releasepilot.config.file_config.validate_config`)
2. Fallback to `jsonschema.Draft7Validator` against the schema file

Invalid config is rejected with actionable error messages displayed in the UI.

### Supported config fields

Each tool defines its own schema. See:
- **ReleasePilot**: `ReleasePilot/schema/releasepilot.schema.json`
- **ReleaseBoard**: `ReleaseBoard/schema/releaseboard.schema.json`

## ReleaseBoard Integration

ReleaseBoard requires a `releaseboard.json` config file. OpsPortal resolves this
file using a multi-strategy search (first match wins):

| Priority | Strategy | Example |
|----------|----------|---------|
| 1 | `OPSPORTAL_RELEASEBOARD_CONFIG` env var | `/etc/opsportal/releaseboard.json` |
| 2 | Inside `repo_path` (if set) | `../ReleaseBoard/releaseboard.json` |
| 3 | Inside per-tool work directory | `work/tools/releaseboard/releaseboard.json` |
| 4 | Inside `OPSPORTAL_TOOLS_BASE_DIR` | `../releaseboard.json` |
| 5 | Current working directory | `./releaseboard.json` |

If no config file is found, the dashboard shows a diagnostic message with
the search locations (sanitized — no raw filesystem paths are exposed to end users).

**For containerized / CI deployments**, set `OPSPORTAL_RELEASEBOARD_CONFIG` to the
absolute path of the mounted config file.

## Application Embedding

OpsPortal embeds child tools in iframes. For this to work, two conditions must be met:

1. **Portal CSP** — OpsPortal's Content-Security-Policy includes `frame-src` directives
   for each tool's origin (built automatically from configured ports).
2. **Tool framing headers** — each tool must allow framing from the portal's origin.
   OpsPortal sets `{TOOL}_ALLOW_FRAMING=true` and `{TOOL}_CORS_ORIGINS` environment
   variables when launching child processes.

### Embedding compatibility model

| App type | Behavior |
|----------|----------|
| **Embeddable** | Rendered in iframe within the portal UI |
| **Non-embeddable** | Fallback UI shown with "Open in New Tab" button |
| **External** | Direct link, no iframe attempted |

If a tool's iframe fails to load (due to CSP, `X-Frame-Options`, or network errors),
the portal displays a clear fallback message with an "Open in New Tab" action. Users
are never shown a blank or cryptic "blocked content" page.

The detection logic handles:
- **Cross-origin frames** (SecurityError on `contentDocument` access) — treated as successful embedding
- **Same-origin blank pages** — content length check with retry after 1 second
- **Error events** — immediate fallback display
- **Timeout** — 15-second deadline triggers fallback if nothing loads

## Iframe Width Controls

When viewing an embedded application, users can expand the iframe width for tools
that need more horizontal space (dashboards, wide tables, etc.).

| Mode | Behavior |
|------|----------|
| **Normal** | Standard container width (1280px max) |
| **Expand Left** | Container stretches to fill left side, reduced right padding |
| **Expand Right** | Container stretches to fill right side, reduced left padding |

Controls appear as a button group above the iframe. The selected width mode is
persisted in `localStorage` (`opsportal_frame_width`) so it survives page reloads.

The skeleton is replaced by the iframe content once the frame fires its `load` event,
or by the fallback UI if loading fails. Transitions use a 0.3s opacity fade.

## Project Structure

```
src/opsportal/
├── __main__.py       # Typer CLI (serve, version)
├── app/
│   ├── factory.py    # create_app() — registers adapters, mounts routes
│   ├── routes.py     # Portal HTML pages + JSON API
│   ├── lifespan.py   # Startup/shutdown lifecycle
│   └── middleware.py  # Security headers (CSP, CSRF, X-Frame-Options)
├── adapters/
│   ├── base.py       # ToolAdapter ABC, enums, dataclasses
│   ├── _config_mixin.py  # JSON schema config read/validate/save
│   ├── registry.py   # AdapterRegistry
│   ├── releaseboard.py   # ReleaseBoard adapter (auto-start, config resolution)
│   └── releasepilot.py   # ReleasePilot adapter
├── services/
│   ├── process_manager.py  # Subprocess lifecycle, health polling
│   ├── artifact_manager.py
│   ├── health.py
│   └── log_store.py
├── config/
│   └── manifest.py   # YAML manifest parser (Pydantic models + validation)
├── core/
│   ├── settings.py   # PortalSettings (pydantic-settings)
│   ├── network.py    # SSL/proxy env propagation, HTTP client factory
│   └── errors.py     # Logging setup
└── ui/
    ├── templates/     # Jinja2 (home, tool_web, tool_error, health, etc.)
    └── static/
        ├── css/       # Design system (portal-base, portal-pages, portal-components)
        └── js/        # i18n engine, translations (EN, PL)
```

## CSP Considerations

OpsPortal generates Content-Security-Policy headers dynamically. Key directives:

| Directive | Value | Purpose |
|-----------|-------|---------|
| `default-src` | `'self'` | Restrict resources to same origin |
| `script-src` | `'self' 'unsafe-inline'` | Allow portal inline scripts |
| `style-src` | `'self' 'unsafe-inline'` | Allow portal inline styles |
| `frame-src` | `http://127.0.0.1:{port} http://localhost:{port}` per tool | Allow iframe embedding of child tools |
| `frame-ancestors` | `'self'` | Prevent the portal itself from being framed |

### Enterprise reverse proxy considerations

If you run OpsPortal behind a reverse proxy (nginx, Traefik, HAProxy):

- **Do not** set your own `Content-Security-Policy` header that overrides `frame-src`
- If you must add CSP at the proxy level, merge OpsPortal's `frame-src` values
- Ensure the proxy forwards `X-Forwarded-For` and `X-Forwarded-Proto` headers
- Do not strip `X-Frame-Options` headers from child tool responses

### Iframe sandbox

The portal uses `sandbox="allow-same-origin allow-scripts allow-forms allow-popups"` on
all iframes. This provides defense-in-depth while allowing tools to function normally.

## Troubleshooting

### "This content is blocked" / embedding failures

**Symptom:** Browser shows a "blocked content" message instead of the embedded tool.

**Causes and fixes:**
1. **Tool not started** — check process logs on the tool error page; verify the CLI binary is installed
2. **CSP mismatch** — check browser DevTools console for `frame-src` or `Refused to frame` errors
3. **Reverse proxy override** — verify the proxy doesn't inject its own CSP that omits the tool's origin
4. **`X-Frame-Options` conflict** — ensure the child tool sets `SAMEORIGIN` or allows framing from the portal origin
5. **SSL interception** — corporate proxies may break WebSocket or iframe connections; see [Corporate Proxy / SSL](#corporate-proxy--ssl)

### ReleaseBoard config not found

**Symptom:** Error page shows "Configuration file 'releaseboard.json' not found."

**Fix:** Create the config file in one of the search locations or set `OPSPORTAL_RELEASEBOARD_CONFIG`:

```bash
export OPSPORTAL_RELEASEBOARD_CONFIG=/path/to/releaseboard.json
```

### Tool fails to start / health check timeout

**Symptom:** Error page shows "Server failed to start or health check timed out."

**Fixes:**
1. Verify the tool's CLI binary is installed: `which releaseboard` or `which releasepilot`
2. Check the tool can start independently: `releaseboard serve --port 8081`
3. Increase startup timeout in `opsportal.yaml` if the tool is slow to boot
4. Check port conflicts: `lsof -i :8081`
5. Review diagnostic logs on the error page

### Admin diagnostics

OpsPortal never exposes raw filesystem paths or internal details in the UI.
All error messages are sanitized — home directory paths are replaced with `~`.
Full diagnostic details are available in:
- Process logs on the tool error page
- The portal's Activity Logs page (`/logs`)
- Server console output (set `OPSPORTAL_LOG_LEVEL=debug` for verbose logging)

## Unified Platform Architecture

Both tools share the same architectural model (defined by ReleaseBoard):

| Convention | Value |
|------------|-------|
| Framework | FastAPI with Jinja2 SSR |
| App factory | `create_app(config, *, root_path="")` |
| Liveness | `GET /health/live` → `{"status": "alive"}` |
| Readiness | `GET /health/ready` → 200 or 503 |
| SSE | Real-time progress via `StreamingResponse` |
| Middleware | Pure ASGI (SecurityHeaders, RequestLogging) |
| Logging | `get_logger(name)` → structured formatter |
| CLI | Typer/Click with `serve` subcommand |
| Iframe support | `{TOOL}_ALLOW_FRAMING=true` env var |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

### Pre-commit Hook

A pre-commit hook is provided that runs lint (with auto-fix), format check, and the full test suite before each commit:

```bash
cp scripts/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

The hook will:
1. **Auto-fix** lint issues on staged files (`ruff check --fix`)
2. **Check formatting** — if issues are found, it auto-formats and exits so you can review and re-stage
3. **Run the test suite** — commit is blocked if any test fails

## CI/CD Pipelines

Production-ready pipeline examples are included for both GitHub Actions and GitLab CI.

### GitHub Actions

File: `.github/workflows/ci.yml`

Stages: lint → test (matrix: Python 3.12, 3.13) → validate config → build package

```bash
# Run locally to match CI behavior:
ruff check src/ tests/
ruff format --check src/ tests/
pytest tests/ -v
python -c "from opsportal.app.settings import PortalSettings; PortalSettings()"
```

### GitLab CI

File: `.gitlab-ci.yml`

Stages: lint → test → validate → build

Both pipelines include:
- **Config validation** — catches schema/config errors before deployment
- **Secure secret handling** — secrets are referenced via CI variables, never hardcoded
- **Proxy-aware builds** — `HTTP_PROXY`/`HTTPS_PROXY`/`SSL_CERT_FILE` can be set as CI variables
- **Artifact publishing** — built wheels are stored as pipeline artifacts

### Running behind a corporate proxy in CI

Set these CI/CD variables (secrets/protected as appropriate):

| Variable | Purpose |
|----------|---------|
| `HTTP_PROXY` | Corporate proxy URL |
| `HTTPS_PROXY` | Corporate proxy URL for HTTPS |
| `NO_PROXY` | Comma-separated bypass list |
| `SSL_CERT_FILE` | Path to CA bundle (mount in runner) |
| `PIP_CERT` | CA bundle for pip installs |

## Corporate Proxy / SSL

OpsPortal launches child tools (ReleaseBoard, ReleasePilot) as subprocesses. Those child tools make outbound HTTPS calls to GitLab, Jira, etc.

**OpsPortal automatically forwards SSL and proxy environment variables** to all child processes. Set the following variables before starting OpsPortal:

<details>
<summary><b>macOS / Linux</b></summary>

```bash
# 1. Export corporate CA certificates (macOS)
security find-certificate -a -p \
  /Library/Keychains/System.keychain \
  /System/Library/Keychains/SystemRootCertificates.keychain \
  > ~/combined-ca-bundle.pem

# On Linux, the CA bundle is usually already available:
#   /etc/ssl/certs/ca-certificates.crt          (Debian/Ubuntu)
#   /etc/pki/tls/certs/ca-bundle.crt            (RHEL/Fedora)
# If your proxy adds its own CA, ask your IT department for the .pem file
# and append it: cat corporate-ca.pem >> ~/combined-ca-bundle.pem

# 2. Configure SSL trust (add to ~/.zshrc or ~/.bashrc to persist)
export SSL_CERT_FILE=~/combined-ca-bundle.pem
export REQUESTS_CA_BUNDLE=~/combined-ca-bundle.pem

# 3. (Optional) Configure proxy
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1,.internal.example.com

# 4. Start OpsPortal — all env vars are forwarded to child tools
opsportal serve
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# 1. Export corporate CA certificate
# Ask your IT department for the corporate CA .pem file, or export it from
# certmgr.msc → Trusted Root Certification Authorities → Certificates
# Right-click → All Tasks → Export → Base-64 encoded X.509 (.CER)
# Save as: %USERPROFILE%\corporate-ca-bundle.pem

# 2. Configure SSL trust (add to your PowerShell profile to persist)
$env:SSL_CERT_FILE = "$env:USERPROFILE\corporate-ca-bundle.pem"
$env:REQUESTS_CA_BUNDLE = "$env:USERPROFILE\corporate-ca-bundle.pem"

# 3. (Optional) Configure proxy
$env:HTTP_PROXY = "http://proxy.example.com:8080"
$env:HTTPS_PROXY = "http://proxy.example.com:8080"
$env:NO_PROXY = "localhost,127.0.0.1,.internal.example.com"

# 4. Start OpsPortal — all env vars are forwarded to child tools
opsportal serve
```

> **Tip:** To make permanent: `[System.Environment]::SetEnvironmentVariable("SSL_CERT_FILE", "$env:USERPROFILE\corporate-ca-bundle.pem", "User")`
</details>

**Forwarded environment variables:**

| Variable | Purpose |
|---|---|
| `SSL_CERT_FILE` | Custom CA bundle for Python's `ssl` module |
| `REQUESTS_CA_BUNDLE` | Custom CA bundle for `requests`-based tools |
| `CURL_CA_BUNDLE` | Custom CA bundle for `curl` |
| `NODE_EXTRA_CA_CERTS` | Custom CA bundle for Node.js tools |
| `HTTP_PROXY` / `http_proxy` | HTTP proxy URL |
| `HTTPS_PROXY` / `https_proxy` | HTTPS proxy URL |
| `NO_PROXY` / `no_proxy` | Hostnames to bypass proxy |

## Remote Tool Sourcing

OpsPortal supports a **managed remote installation model** where tools like
ReleaseBoard and ReleasePilot are installed from remote Git repositories rather
than requiring manually cloned local source checkouts.

### How it works

1. Each tool in `opsportal.yaml` has an optional `source:` block declaring its
   Git repository, ref/tag, package name, and install strategy.
2. On startup, OpsPortal checks if each tool's CLI is available on `$PATH`.
3. If not, and a `source:` is defined, OpsPortal runs:
   ```
   pip install git+https://github.com/OWNER/REPO.git@REF[extras]
   ```
4. A per-tool **work directory** (`work/tools/{slug}/`) is created for config
   files and data. This replaces `repo_path` as the working directory.

### Offline / restricted environments

If the environment has no internet access:
1. Pre-install tools using `pip install` with local wheels or an internal registry
2. Set `install_strategy: pre_installed` in `opsportal.yaml`
3. OpsPortal verifies the CLI is available but does not attempt network downloads

For proxy environments, standard `HTTP_PROXY`/`HTTPS_PROXY` variables are
propagated to `pip install` automatically.

### Backward compatibility

Setting `repo_path:` still works and takes precedence over `work_dir` for CWD.
This enables local development workflows where you edit tool source directly:

```yaml
tools:
  releasepilot:
    source:
      repository: POLPROG-TECH/ReleasePilot
      ref: v1.1.0
      package: releasepilot
    repo_path: ../ReleasePilot  # local dev override
```

## Migration Notes

### Upgrading to remote-managed tool sourcing

**repo_path is now optional** — tools with a `source:` block no longer require
`repo_path`. If you currently use `repo_path: ReleasePilot`, you can either:
- Remove it and rely on the `source:` block for production
- Keep it alongside `source:` for local development

**work_dir replaces repo_path for CWD** — when `repo_path` is not set, the tool
process runs from `work/tools/{slug}/` instead of a repo checkout directory.
Config files are stored there too.

**tools_base_dir is legacy** — the `OPSPORTAL_TOOLS_BASE_DIR` env var still works
for resolving relative `repo_path` values, but is not needed for remote-managed tools.

### Upgrading from pre-v0.x (before enterprise features)

**Config resolution** — ReleaseBoard config is no longer resolved via a single
hardcoded path. If you relied on the tool finding `releaseboard.json` inside
`repo_path`, this still works. To use a different location, set
`OPSPORTAL_RELEASEBOARD_CONFIG=/path/to/releaseboard.json`.

**Product card HTML** — the CSS classes `product-action`, `product-action-launch`,
`product-action-open`, `product-action-setup` have been removed. If you have custom
themes targeting these selectors, migrate to `.product-version`,
`.product-status-label`, and `.product-meta-badge`.

**New CSS classes** — the following were added and must be present in any custom theme:
- `.product-meta`, `.product-meta-badge`, `.product-meta-web`, `.product-meta-config` — card metadata badges
- `.iframe-controls`, `.iframe-control-btn` — iframe width expansion controls
- `.iframe-skeleton`, `.skeleton-shimmer`, `.skeleton-card`, `.skeleton-row`, `.skeleton-block` — loading skeleton
- `.container.frame-expand-left`, `.container.frame-expand-right` — iframe width modes

**CSP headers** — the portal now emits `frame-src` directives. If you have a reverse
proxy that sets its own CSP, merge the portal's `frame-src` values or remove the
proxy-level override.

**i18n keys** — three new keys added: `tool.expand_left`, `tool.expand_right`, `tool.reset_width`.
If you maintain custom translations, add these keys.

**Log sanitization** — process logs displayed on error pages now replace home directory
paths with `~`. This is a display-only change; actual log content is unchanged.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).