"""Admin API routes - config, versioning, audit, scheduler, notifications."""

from __future__ import annotations

import json

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from opsportal.app.routes_api import (
    _audit_log,
    _cache,
    _config_versions,
    _registry,
)
from opsportal.core.errors import get_logger

router = APIRouter()

logger = get_logger("app.routes_admin")


# ---------------------------------------------------------------------------
# Config Import/Export
# ---------------------------------------------------------------------------


@router.get("/api/config/export")
async def api_config_export(request: Request):
    """Export full portal configuration as YAML."""
    from fastapi.responses import PlainTextResponse

    settings = request.app.state.settings
    manifest_path = settings.manifest_path
    if not manifest_path.exists():
        raise HTTPException(404, "Manifest file not found")

    manifest_content = manifest_path.read_text(encoding="utf-8")

    tool_configs = {}
    for adapter in _registry(request).all():
        cfg = adapter.get_config()
        if cfg:
            tool_configs[adapter.slug] = cfg

    export_data = {
        "manifest": yaml.safe_load(manifest_content),
        "tool_configs": tool_configs,
    }
    content = yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
    return PlainTextResponse(
        content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=opsportal-export.yaml"},
    )


@router.post("/api/config/import")
async def api_config_import(request: Request):
    """Import portal configuration from YAML."""
    try:
        body = await request.body()
        data = yaml.safe_load(body.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError, ValueError) as exc:
        return JSONResponse(
            {"success": False, "error": f"Invalid YAML: {exc}"},
            status_code=400,
        )

    if "manifest" in data:
        settings = request.app.state.settings
        manifest_yaml = yaml.dump(data["manifest"], default_flow_style=False, allow_unicode=True)
        settings.manifest_path.write_text(manifest_yaml, encoding="utf-8")

    if "tool_configs" in data:
        for slug, cfg in data["tool_configs"].items():
            adapter = _registry(request).get(slug)
            if adapter:
                adapter.save_config(cfg)

    _audit_log(request).record(
        category="config",
        action="import",
        details={"keys": list(data.keys())},
    )
    return JSONResponse({"success": True, "message": "Configuration imported"})


# ---------------------------------------------------------------------------
# Config Versioning
# ---------------------------------------------------------------------------


@router.get("/api/tools/{slug}/config/versions")
async def api_config_versions(request: Request, slug: str):
    versions = _config_versions(request).list_versions(slug)
    return JSONResponse([v.to_dict() for v in versions])


@router.get("/api/tools/{slug}/config/versions/{version_id}")
async def api_config_version_content(request: Request, slug: str, version_id: str):
    content = _config_versions(request).get_version_content(slug, version_id)
    if content is None:
        raise HTTPException(404, "Version not found")
    return JSONResponse(content)


@router.post("/api/tools/{slug}/config/restore/{version_id}")
async def api_config_restore(request: Request, slug: str, version_id: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    config_path = adapter.config_file_path()
    if not config_path:
        return JSONResponse({"success": False, "error": "No config file path"})

    if config_path.exists():
        _config_versions(request).snapshot(slug, config_path, actor="restore")

    ok = _config_versions(request).restore(slug, version_id, config_path)
    _audit_log(request).record(
        category="config",
        action="restore",
        tool_slug=slug,
        details={"version_id": version_id, "success": ok},
    )
    return JSONResponse({"success": ok})


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


@router.get("/api/audit")
async def api_audit_log(request: Request):
    category = request.query_params.get("category")
    limit = int(request.query_params.get("limit", "100"))
    entries = _audit_log(request).recent(limit=limit, category=category)
    return JSONResponse([e.to_dict() for e in entries])


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


@router.get("/api/scheduler/jobs")
async def api_scheduler_jobs(request: Request):
    scheduler = request.app.state.scheduler
    jobs = scheduler.list_jobs()
    return JSONResponse([j.to_dict() for j in jobs])


@router.post("/api/scheduler/jobs")
async def api_scheduler_add_job(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    scheduler = request.app.state.scheduler
    job = scheduler.add_job(
        tool_slug=body["tool_slug"],
        action_name=body["action_name"],
        cron_expr=body["cron_expr"],
        params=body.get("params"),
    )
    _audit_log(request).record(
        category="scheduler",
        action="add_job",
        tool_slug=body["tool_slug"],
        details={"job_id": job.job_id, "cron_expr": body["cron_expr"]},
    )
    return JSONResponse(job.to_dict())


@router.delete("/api/scheduler/jobs/{job_id}")
async def api_scheduler_remove_job(request: Request, job_id: str):
    ok = request.app.state.scheduler.remove_job(job_id)
    return JSONResponse({"success": ok})


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@router.get("/api/notifications")
async def api_notifications(request: Request):
    return JSONResponse(request.app.state.notification_service.recent())


@router.post("/api/notifications/test")
async def api_notification_test(request: Request):
    from opsportal.services.notification_service import NotificationLevel

    await request.app.state.notification_service.notify(
        level=NotificationLevel.INFO,
        title="Test Notification",
        message="This is a test notification from OpsPortal.",
        event_type="all",
    )
    return JSONResponse({"success": True})


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


@router.get("/api/registry/plugins")
async def api_available_plugins(request: Request):
    loader = request.app.state.plugin_loader
    return JSONResponse({"plugins": loader.available_plugins})


# ---------------------------------------------------------------------------
# Per-tool Config CRUD
# ---------------------------------------------------------------------------


@router.get("/api/tools/{slug}/config")
async def api_tool_config(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)

    cache = _cache(request)
    cache_key = f"schema:{slug}"
    schema = cache.get(cache_key)
    if schema is None:
        schema = adapter.config_schema()
        if schema:
            cache.set(cache_key, schema)

    data = adapter.get_config()
    config_path = adapter.config_file_path()
    return JSONResponse(
        {
            "slug": slug,
            "configurable": schema is not None,
            "schema": schema,
            "values": data,
            "config_file": str(config_path) if config_path else None,
        }
    )


@router.post("/api/tools/{slug}/config/validate")
async def api_tool_config_validate(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)
    result = adapter.validate_config(body)
    return JSONResponse({"valid": result.valid, "errors": result.errors})


@router.put("/api/tools/{slug}/config")
async def api_tool_config_save(request: Request, slug: str):
    adapter = _registry(request).get(slug)
    if not adapter:
        raise HTTPException(404)
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    config_path = adapter.config_file_path()
    if config_path and config_path.exists():
        _config_versions(request).snapshot(slug, config_path)
    elif adapter.get_config():
        _config_versions(request).snapshot_content(slug, adapter.get_config())

    result = adapter.save_config(body)
    _audit_log(request).record(
        category="config",
        action="save_config",
        tool_slug=slug,
        details={"success": result.success, "error": result.error},
    )
    _cache(request).delete(f"schema:{slug}")

    return JSONResponse(
        {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }
    )


# ---------------------------------------------------------------------------
# Alert Rules API
# ---------------------------------------------------------------------------


@router.get("/api/alerts/rules")
async def api_alert_rules(request: Request):
    mgr = request.app.state.alert_manager
    return JSONResponse([r.to_dict() for r in mgr.list_rules()])


@router.post("/api/alerts/rules")
async def api_add_alert_rule(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    mgr = request.app.state.alert_manager
    rule = mgr.add_rule(**body)
    _audit_log(request).record(category="alerts", action="add_rule", details=rule.to_dict())
    return JSONResponse(rule.to_dict())


@router.delete("/api/alerts/rules/{rule_id}")
async def api_delete_alert_rule(request: Request, rule_id: str):
    ok = request.app.state.alert_manager.remove_rule(rule_id)
    return JSONResponse({"success": ok})


@router.get("/api/alerts/active")
async def api_active_alerts(request: Request):
    mgr = request.app.state.alert_manager
    return JSONResponse([a.to_dict() for a in mgr.active_alerts()])


@router.post("/api/alerts/acknowledge")
async def api_acknowledge_alert(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    ok = request.app.state.alert_manager.acknowledge(body["rule_id"], body["tool_slug"])
    return JSONResponse({"success": ok})


# ---------------------------------------------------------------------------
# Backup & Restore API
# ---------------------------------------------------------------------------


@router.post("/api/backups")
async def api_create_backup(request: Request):
    label = ""
    try:
        body = await request.json()
        label = body.get("label", "")
    except (ValueError, TypeError, KeyError) as exc:
        logger.debug("Could not parse backup label from request body: %s", exc)
    backup = request.app.state.backup_service.create_backup(label)
    _audit_log(request).record(
        category="backup",
        action="create",
        details=backup.to_dict(),
    )
    return JSONResponse(backup.to_dict())


@router.get("/api/backups")
async def api_list_backups(request: Request):
    backups = request.app.state.backup_service.list_backups()
    return JSONResponse([b.to_dict() for b in backups])


@router.post("/api/backups/{filename}/restore")
async def api_restore_backup(request: Request, filename: str):
    ok = request.app.state.backup_service.restore_backup(filename)
    _audit_log(request).record(
        category="backup",
        action="restore",
        details={"filename": filename, "success": ok},
    )
    return JSONResponse({"success": ok})


@router.delete("/api/backups/{filename}")
async def api_delete_backup(request: Request, filename: str):
    ok = request.app.state.backup_service.delete_backup(filename)
    return JSONResponse({"success": ok})


# ---------------------------------------------------------------------------
# SLA Reporting API
# ---------------------------------------------------------------------------


@router.get("/api/sla/report")
async def api_sla_report(request: Request):
    reporter = request.app.state.sla_reporter
    tracker = request.app.state.uptime_tracker
    report = reporter.generate_report(tracker)
    return JSONResponse(report.to_dict())


@router.get("/api/sla/report/csv")
async def api_sla_csv(request: Request):
    from fastapi.responses import PlainTextResponse

    reporter = request.app.state.sla_reporter
    tracker = request.app.state.uptime_tracker
    report = reporter.generate_report(tracker)
    csv_content = reporter.report_to_csv(report)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sla-report.csv"},
    )


@router.get("/api/sla/targets")
async def api_sla_targets(request: Request):
    reporter = request.app.state.sla_reporter
    return JSONResponse([t.to_dict() for t in reporter.get_targets()])


@router.post("/api/sla/targets")
async def api_set_sla_target(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    reporter = request.app.state.sla_reporter
    target = reporter.set_target(
        tool_slug=body["tool_slug"],
        target_percent=body.get("target_percent", 99.9),
        name=body.get("name", ""),
    )
    return JSONResponse(target.to_dict())


# ---------------------------------------------------------------------------
# RBAC User Management API
# ---------------------------------------------------------------------------


@router.get("/api/users")
async def api_list_users(request: Request):
    mgr = request.app.state.auth_manager
    return JSONResponse([u.to_dict() for u in mgr.list_users()])


@router.post("/api/users")
async def api_create_user(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    from opsportal.services.auth_manager import Role

    mgr = request.app.state.auth_manager
    user = mgr.add_user(
        body["username"],
        body["password"],
        Role(body.get("role", "viewer")),
    )
    _audit_log(request).record(
        category="users",
        action="create",
        details={"username": user.username, "role": user.role},
    )
    return JSONResponse(user.to_dict())


@router.delete("/api/users/{username}")
async def api_delete_user(request: Request, username: str):
    ok = request.app.state.auth_manager.remove_user(username)
    return JSONResponse({"success": ok})


@router.put("/api/users/{username}/role")
async def api_update_user_role(request: Request, username: str):
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    from opsportal.services.auth_manager import Role

    ok = request.app.state.auth_manager.update_role(username, Role(body["role"]))
    return JSONResponse({"success": ok})


# ---------------------------------------------------------------------------
# Operations Overview toggle
# ---------------------------------------------------------------------------


@router.get("/api/config/ops-overview")
async def api_ops_overview_status(request: Request):
    """Return current Operations Overview enabled state."""
    enabled = request.app.state.settings.ops_overview_enabled
    return JSONResponse({"enabled": enabled})


@router.put("/api/config/ops-overview")
async def api_ops_overview_toggle(request: Request):
    """Toggle Operations Overview on or off at runtime.

    Persists the value to ``portal_state.json`` so it survives restarts.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    enabled = bool(body.get("enabled", False))
    # Update in-memory settings
    object.__setattr__(request.app.state.settings, "ops_overview_enabled", enabled)
    # Persist to disk so the value survives restarts
    request.app.state.portal_state.set("ops_overview_enabled", enabled)
    _audit_log(request).record(
        category="config",
        action="toggle_ops_overview",
        details={"enabled": enabled},
    )
    logger.info("Operations Overview %s", "enabled" if enabled else "disabled")
    return JSONResponse({"success": True, "enabled": enabled, "persisted": True})
