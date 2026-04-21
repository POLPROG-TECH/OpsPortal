/* ============================================================
   OpsPortal \u2014 Internationalisation
   Translation dictionary + i18n engine (extracted from portal.js)
   ============================================================ */

(function () {
  "use strict";

  /* ================================================================
     Translations
     ================================================================ */

  var T = {
    en: {
      /* ---------- actions / lifecycle ---------- */
      "action.completed_in":        "Completed in ",
      "action.completed_ok":        "Action completed successfully.",
      "action.completed_toast":     " completed",
      "action.failed":              "Action failed.",
      "action.failed_toast":        " failed: ",
      "action.network_error":       "Network error: ",
      "action.request_failed":      "Request failed: ",
      "action.running":             "Running\u2026",
      "action.running_toast":       "Running ",
      "action.unknown_error":       "Unknown error",
      "action.view_artifact":       "View artifact",

      /* ---------- breadcrumb ---------- */
      "breadcrumb.home":            "OpsPortal",

      /* ---------- cards ---------- */
      "card.configure":             "Configure",
      "card.launch":                "Launch \u2192",
      "card.open":                  "Open dashboard \u2192",
      "card.setup":                 "Setup required",

      /* ---------- CLI tool page ---------- */
      "cli.actions":                "Actions",
      "cli.all_artifacts":          "All Artifacts",
      "cli.clear":                  "Clear",
      "cli.dashboard":              "Dashboard",
      "cli.no_actions":             "No actions available.",
      "cli.no_dashboard":           "No dashboard generated yet.",
      "cli.no_dashboard_hint":      "Run an action below to generate a dashboard.",
      "cli.open_fullscreen":        "Open Full Screen \u2197",
      "cli.output":                 "Output",
      "cli.output_placeholder":     "Run an action to see output here.",
      "cli.run":                    "Run",

      /* ---------- configuration ---------- */
      "config.apply_json":          "Apply JSON to Form",
      "config.artifact_dir":        "Artifact Directory",
      "config.back":                "Back to app",
      "config.comma_separated":     "comma-separated values",
      "config.config_valid_toast":  "Configuration is valid",
      "config.debug":               "Debug",
      "config.default_option":      "\u2014 default \u2014",
      "config.default_prefix":      "default: ",
      "config.edit":                "Edit Configuration",
      "config.form_reset_toast":    "Form reset to last saved values",
      "config.form_view":           "Form View",
      "config.host":                "Host",
      "config.invalid":             "Configuration has validation errors.",
      "config.invalid_json":        "Invalid JSON: ",
      "config.json_applied":        "JSON applied to form",
      "config.load_error":          "Failed to load configuration.",
      "config.loading_schema":      "Loading schema\u2026",
      "config.log_level":           "Log Level",
      "config.manifest_path":       "Manifest Path",
      "config.no_file":             "No configuration file yet \u2014 save to create one.",
      "config.no_properties":       "No configurable properties.",
      "config.not_configurable":    "This application does not support configuration editing.",
      "config.optional":            "optional",
      "config.port":                "Port",
      "config.portal_settings":     "Portal Settings",
      "config.raw_json":            "Raw JSON",
      "config.required":            "required",
      "config.reset":               "Reset",
      "config.save":                "Save",
      "config.save_error":          "Failed to save configuration.",
      "config.save_failed_toast":   "Save failed",
      "config.save_request_failed": "Save request failed: ",
      "config.saved":               "Configuration saved successfully.",
      "config.saved_toast":         "Saved",
      "config.saving":              "Saving\u2026",
      "config.setting":             "Setting",
      "config.restart_hint":        "Configuration saved. Restart the tool to apply changes.",
      "config.restart_now":         "Restart Now",
      "config.restarting":          "Restarting tool\u2026",
      "config.restart_success":     "Tool restarted successfully. Changes are now active.",
      "config.restart_failed":      "Restart failed: ",
      "config.restart_request_failed": "Restart request failed: ",
      "config.save_restart":        "Save & Restart",
      "config.sync_json":           "Sync Form \u2192 JSON",
      "config.title":               "Configuration",
      "config.tool_color":          "Color",
      "config.tool_icon":           "Icon",
      "config.tool_mode":           "Mode",
      "config.tool_name":           "Name",
      "config.tool_slug":           "Slug",
      "config.tools_base_dir":      "Tools Base Directory",
      "config.valid":               "Configuration is valid.",
      "config.validate":            "Validate",
      "config.validation_errors":   "Validation errors:",
      "config.validation_failed":   "Validation request failed: ",
      "config.validating":          "Validating\u2026",
      "config.value":               "Value",
      "config.work_dir":            "Work Directory",

      /* ---------- empty states ---------- */
      "empty.add_tools":            "Add tools to <code>opsportal.yaml</code> to get started.",
      "empty.no_apps":              "No applications registered",

      /* ---------- error pages ---------- */
      "error.back_to_dashboard":    "Back to Dashboard",
      "error.back_to_portal":       "Back to Portal",
      "error.badge":                "error",
      "error.diagnostic_logs":      "Diagnostic Logs",
      "error.failed_to_start":      "Failed to Start",
      "error.retry":                "Retry",
      "error.something_wrong":      "Something went wrong",
      "error.unexpected":           "An unexpected error occurred.",

      /* ---------- footer ---------- */
      "footer.text":                "\u00a9 POLPROG \u00b7 OpsPortal \u2014 Engineering Operations Platform",
      "footer.rights":              "All rights reserved.",
      "footer.built_with":          "Dashboard built with",

      /* ---------- gear menu ---------- */
      "gear.language":              "Language",
      "gear.settings_title":        "Settings",
      "gear.theme":                 "Theme",

      /* ---------- health page ---------- */
      "health.all_ok":              "All systems operational",
      "health.errors":              "Errors:",
      "health.healthy":             "Healthy",
      "health.issues_detected":     "Issues detected",
      "health.no_tools":            "No tools registered for health checks.",
      "health.status":              "Health Status",
      "health.unhealthy":           "Unhealthy",

      /* ---------- hero ---------- */
      "hero.subtitle":              "Your unified entry point to the engineering operations toolkit. Launch, monitor, and manage your tools from a single dashboard.",
      "hero.title":                 "Welcome to OpsPortal",

      /* ---------- logs page ---------- */
      "logs.action":                "Action",
      "logs.activity_log":          "Activity Log",
      "logs.level":                 "Level",
      "logs.message":               "Message",
      "logs.no_entries":            "No log entries yet.",
      "logs.no_entries_hint":       "Activity will appear here as you interact with tools.",
      "logs.refresh":               "\u21bb Refresh",
      "logs.time":                  "Time",
      "logs.tool":                  "Tool",

      /* ---------- modals ---------- */
      "modal.cancel":               "Cancel",
      "modal.close":                "Close",
      "modal.confirm":              "Confirm",
      "modal.dangerous.message":    "This is a potentially dangerous action. Are you sure you want to proceed?",
      "modal.dangerous.title":      "Confirm Action",
      "modal.stop.message":         "Are you sure you want to stop this tool? The embedded application will become unavailable.",
      "modal.stop.title":           "Stop Application",

      /* ---------- navigation ---------- */
      "nav.home":                    "Home",
      "nav.dashboard":              "Dashboard",
      "nav.health":                 "Health",
      "nav.logs":                   "Logs",
      "nav.settings":               "Settings",
      "nav.config":                 "Config",
      "nav.sla":                    "SLA Report",

      /* ---------- sidebar ---------- */
      "sidebar.main":               "Main",
      "sidebar.monitoring":         "Monitoring",
      "sidebar.tools":              "Tools",

      /* ---------- dashboard ---------- */
      "dashboard.title":            "Monitoring Dashboard",
      "dashboard.subtitle":         "Real-time metrics and performance charts",
      "dashboard.total_tools":      "Total Tools",
      "dashboard.running":          "Running",
      "dashboard.stopped":          "Stopped",
      "dashboard.active_alerts":    "Active Alerts",
      "dashboard.chart_cpu_memory": "CPU & Memory Usage",
      "dashboard.chart_latency":    "Response Latency (ms)",
      "dashboard.chart_uptime":     "Uptime %",
      "dashboard.chart_alerts":     "Active Alerts",
      "dashboard.loading_alerts":   "Loading alerts\u2026",
      "dashboard.no_alerts":        "No active alerts \u2713",
      "dashboard.label_cpu":        "CPU %",
      "dashboard.label_memory":     "Memory (MB)",
      "dashboard.label_latency":    "Avg Latency (ms)",
      "dashboard.label_uptime":     "Uptime %",

      /* ---------- sla report ---------- */
      "sla.title":                  "SLA Report",
      "sla.generated":              "Generated:",
      "sla.period":                 "Period:",
      "sla.export_csv":             "Export CSV",
      "sla.overall_uptime":         "Overall Uptime",
      "sla.meeting_sla":            "Meeting SLA",
      "sla.below_sla":              "Below SLA",
      "sla.total_tools":            "Total Tools",
      "sla.col_tool":               "Tool",
      "sla.col_target":             "Target",
      "sla.col_actual":             "Actual",
      "sla.col_gap":                "Gap",
      "sla.col_checks":             "Checks",
      "sla.col_latency":            "Latency",
      "sla.col_incidents":          "Incidents",
      "sla.col_status":             "Status",
      "sla.badge_ok":               "\u2713 OK",
      "sla.badge_breach":           "\u2717 Breach",

      /* ---------- admin config page ---------- */
      "admin.subtitle":             "Portal configuration and feature management. Changes take effect immediately.",
      "admin.ops_overview":         "Operations Overview",
      "admin.ops_overview_desc":    "When enabled, the Home page displays an integrated dashboard with widgets for Release Calendar, Tags Overview, JSON Translation, and Release Notes from all connected tools. Disabled by default.",
      "admin.ops_overview_enable":  "Enable Operations Overview",
      "admin.ops_overview_help":    "Setting is saved and persists across restarts. Initial default can be set via",
      "admin.enabled":              "Enabled",
      "admin.disabled":             "Disabled",
      "admin.saving":               "Saving\u2026",
      "admin.saved_suffix":         "\u2713 Saved",
      "admin.save_failed":          "Save failed",

      /* ---------- config section labels ---------- */
      "config.section.general":     "General",
      "config.section.source":      "Source Control",
      "config.section.output":      "Output & Display",
      "config.section.connectivity":"Connectivity & Tokens",
      "config.section.ci":          "CI / CD",
      "config.section.display":     "Display",
      "config.section.advanced":    "Advanced",

      /* ---------- activity feed ---------- */
      "feed.title":                 "Live Activity",

      /* ---------- dependency graph ---------- */
      "nav.depgraph":               "Dependencies",
      "depgraph.title":             "Dependency Graph",
      "depgraph.subtitle":          "Visualize relationships between tools and services",
      "depgraph.reset":             "Reset View",
      "depgraph.show_labels":       "Show labels",

      /* ---------- onboarding ---------- */
      "onboarding.close":           "Close",
      "onboarding.get_started":     "Get Started",
      "onboarding.next":            "Next",
      "onboarding.skip":            "Skip",
      "onboarding.start":           "Get Started",
      "onboarding.step1.text":      "OpsPortal is the single entry point for four internal tools. Each tile on the dashboard represents a distinct application you can launch and use.",
      "onboarding.step1.title":     "Your engineering operations hub",
      "onboarding.step2.text":      "Click any application card to auto-start it. OpsPortal manages the lifecycle \u2014 it launches the app, checks health, and embeds it in the portal. Use the top navigation to return here anytime.",
      "onboarding.step2.title":     "Click a tile to launch",
      "onboarding.step3.text":      "Status indicators on each card show whether an app is running, idle, or needs setup. The Health page gives a full system overview. The Settings page shows portal configuration.",
      "onboarding.step3.title":     "Monitor health & configuration",
      "onboarding.title":           "Welcome to OpsPortal",

      /* ---------- page titles ---------- */
      "page.config":                "Configuration",
      "page.health":                "Health",
      "page.logs":                  "Logs",

      /* ---------- portal config table ---------- */
      "config.registered_tools":    "Registered Tools",

      /* ---------- sections ---------- */
      "section.apps":               "Applications",
      "section.config_issues":      "Configuration Issues",

      /* ---------- stats ---------- */
      "stats.apps":                 "Apps",
      "stats.attention":            "Needs Attention",
      "stats.running":              "Running",

      /* ---------- status ---------- */
      "status.running":             "Running",
      "status.stopped":             "Stopped",
      "status.starting":            "Starting",
      "status.error":               "Error",
      "status.idle":                "Idle",
      "status.ready":               "Ready",
      "status.needs_config":        "Needs configuration",
      "status.not_running":         "Not running",

      /* ---------- theme ---------- */
      "theme.dark":                 "Dark",
      "theme.light":                "Light",
      "theme.midnight":             "Midnight",
      "theme.system":               "System",

      /* ---------- tool controls ---------- */
      "tool.artifacts":             "Artifacts",
      "tool.configure":             "Configure",
      "tool.embed_blocked":         "This application cannot be embedded",
      "tool.embed_blocked_hint":    "The application may restrict iframe embedding due to security policies. You can open it directly in a new browser tab.",
      "tool.not_running":           "Server is not running.",
      "tool.open_new_tab":          "Open in New Tab ↗",
      "tool.retry_embed":           "Retry",
      "tool.proc_logs":             "Process Logs",
      "tool.restart":               "Restart Server",
      "tool.start":                 "Start Server",
      "tool.start_btn":             "Start",
      "tool.start_hint":            "Start the tool to load its web interface.",
      "tool.stop":                  "Stop Server",
      "tool.expand_left":           "Expand Left",
      "tool.expand_right":          "Expand Right",
      "tool.reset_width":           "Normal",

      /* ---------- action names (for toasts) ---------- */
      "action.name.start":          "Start",
      "action.name.stop":           "Stop",
      "action.name.restart":        "Restart",
      "action.name.start_server":   "Start Server",
      "action.name.stop_server":    "Stop Server",
      "action.name.restart_server": "Restart Server",

      /* ---------- health messages ---------- */
      "health.alive":               "Alive",
      "health.process_not_running": "Process not running",
      "health.ok":                  "OK",
      "health.tool_available":      "Tool available",
      "health.connection_error":    "Connection error",
      "health.overall_healthy":     "All systems healthy",
      "health.overall_unhealthy":   "Issues detected",

      /* ---------- log levels ---------- */
      "log.level.info":             "INFO",
      "log.level.warning":          "WARNING",
      "log.level.error":            "ERROR",
      "log.level.debug":            "DEBUG",

      /* ---------- adapter descriptions ---------- */
      "adapter.releasepilot.desc":  "Release notes generator \u2014 from git history to polished documents",
      "adapter.releaseboard.desc":  "Release readiness dashboard \u2014 track branch status across repos",
      "adapter.localesync.desc":    "Translation file sync \u2014 keep locale files consistent",
      "adapter.flowboard.desc":     "Jira flow-metrics dashboard \u2014 cycle time, throughput, CFD & more",

      /* ---------- config / validation ---------- */
      "config.dir_required":        "Directory is required",
      "config.source_required":     "Source locale is required",
      "config.invalid_locale":      "Invalid locale code",
      "config.unknown_property":    "Unknown property",

      /* ---------- error defaults ---------- */
      "error.tool_not_found":       "Tool not found",
      "error.action_not_supported": "Action not supported",

      /* ---------- page titles (document.title) ---------- */
      "page.title.home":            "OpsPortal - Engineering Operations Platform",
      "page.title.health":          "Health - OpsPortal",
      "page.title.logs":            "Logs - OpsPortal",
      "page.title.config":          "Configuration - OpsPortal",
      "page.title.error":           "Error - OpsPortal",
      "page.title.dashboard":       "Dashboard - OpsPortal",
      "page.title.sla":             "SLA Report - OpsPortal",
      "page.title.depgraph":        "Dependencies - OpsPortal",

      /* ---------- aria / accessibility ---------- */
      "aria.main_nav":              "Main navigation",
      "aria.activity_log":          "Activity log",
      "aria.portal_settings":       "Portal settings",
      "aria.registered_tools":      "Registered tools",
      "aria.raw_json_config":       "Raw JSON configuration",

      /* ---------- units ---------- */
      "unit.kb":                    "KB",
      "unit.ms":                    "ms",

      /* ---------- bulk actions ---------- */
      "bulk.start_all":             "Start All",
      "bulk.stop_all":              "Stop All",
      "bulk.restart_all":           "Restart All",
      "bulk.title":                 "Bulk Action",
      "bulk.confirm_stop":          "Are you sure you want to stop ALL tools? All embedded applications will become unavailable.",
      "bulk.confirm_action":        "Are you sure you want to {action} all tools?",
      "bulk.running":               "Running {action} on all tools\u2026",
      "bulk.completed":             "{n}/{total} tools completed successfully",
      "bulk.waiting":               "Waiting\u2026",
      "bulk.queued":                "Queued",
      "bulk.starting":              "Starting\u2026",
      "bulk.stopping":              "Stopping\u2026",
      "bulk.error_prefix":          "Error",
      "bulk.tools_started":         "{n} / {total} tools started",
      "bulk.tools_stopped":         "{n} / {total} tools stopped",

      /* ---------- fullscreen ---------- */
      "tool.fullscreen":            "Fullscreen",
      "tool.exit_fullscreen":       "Exit Fullscreen",
      "tool.open_new_tab_short":    "New Tab",

      /* ---------- command palette ---------- */
      "cmd.no_results":             "No results",
      "cmd.start_tool":             "Start {name}",
      "cmd.stop_tool":              "Stop {name}",
      "cmd.action_executed":        "{label} executed",
      "cmd.action_failed":          "{label} failed",

      /* ---------- uptime ---------- */
      "nav.uptime":                 "Uptime",
      "page.title.uptime":          "Uptime \u2014 OpsPortal",
      "uptime.title":               "Uptime Dashboard",
      "uptime.subtitle":            "Historical availability and incident timeline for all tools.",
      "uptime.checks":              "Checks",
      "uptime.healthy":             "Healthy",
      "uptime.avg_latency":         "Avg Latency",
      "uptime.status":              "Status",
      "uptime.up":                  "Up",
      "uptime.down":                "Down",
      "uptime.recent_incidents":    "Recent Incidents",
      "uptime.ongoing":             "Ongoing",
      "uptime.no_data":             "No uptime data yet.",
      "uptime.no_tools":            "No tools registered for monitoring.",

      /* ---------- drag & drop ---------- */
      "drag.hint":                  "Drag to reorder",

      /* ---------- operations overview ---------- */
      "ops.section_title":          "Operations Overview",
      "ops.refresh":                "Refresh",
      "ops.calendar_title":         "Release Calendar",
      "ops.tags_title":             "Tags Overview",
      "ops.quick_actions":          "Quick Actions",
      "ops.loading_milestones":     "Loading milestones\u2026",
      "ops.loading_tags":           "Loading tags\u2026",
      "ops.no_milestones":          "No upcoming milestones",
      "ops.no_tags":                "No tags data available",
      "ops.no_analysis":            "No analysis data yet",
      "ops.start_tool":             "Start {tool}",
      "ops.to_load_calendar":       "to load calendar data",
      "ops.to_see_tags":            "to see tags",
      "ops.open_releaseboard_calendar": "Open ReleaseBoard to configure release schedule \u2192",
      "ops.open_releaseboard_analysis": "Open {tool} and run analysis \u2192",
      "ops.view_full_calendar":     "View full calendar \u2192",
      "ops.view_in_releaseboard":   "View in ReleaseBoard \u2192",
      "ops.sources_unavailable":    "{n} source(s) unavailable",
      "ops.more_items":             "{n} more\u2026",
      "ops.could_not_load":         "Could not load {name} data.",
      "ops.retry":                  "Retry",
      "ops.generate_release_notes": "Generate Release Notes",
      "ops.translate_json":         "Translate JSON",
      "ops.modal_rn_title":         "Generate Release Notes",
      "ops.modal_tr_title":         "Translate JSON",
      "ops.audience":               "Audience",
      "ops.format":                 "Format",
      "ops.generate":               "Generate",
      "ops.generating":             "Generating\u2026",
      "ops.generation_failed":      "Generation failed",
      "ops.generated_summary":      "Generated: {succeeded}/{total} repos across {apps} app(s)",
      "ops.target_language":        "Target Language",
      "ops.json_input":             "JSON Input",
      "ops.translate":              "Translate",
      "ops.translating":            "Translating {keys} keys to {lang}\u2026",
      "ops.translation_complete":   "Translation complete!",
      "ops.download_json":          "Download translated JSON",
      "ops.copy_clipboard":         "Copy to clipboard",
      "ops.copied":                 "Copied!",
      "ops.loading_languages":      "Loading languages\u2026",
      "ops.no_languages":           "No languages available",
      "ops.languages_failed":       "Failed to load languages",
      "ops.translation_unavailable":"Translation service unavailable. Ensure LocaleSync is installed and running.",
      "ops.drop_json":              "Drop a .json file here or click to browse",
      "ops.no_repos":               "No repositories found.",
      "ops.open_tool_config":       "Open ReleaseBoard to configure repositories and run analysis first.",
      "ops.view_timeline":          "Timeline",
      "ops.view_table":             "Table",
      "ops.days_today":             "Today",
      "ops.days_ago":               "{n}d ago",
      "ops.days_in":                "in {n}d",
      "ops.tag_no_tags":            "No tags",
      "ops.tag_today":              "today",
      "ops.connected":              "connected",
      "ops.no_tools_available":     "no tools available",
      "ops.service_unavailable":    "service unavailable",
      "ops.phase.feature_freeze":   "Feature Freeze",
      "ops.phase.code_freeze":      "Code Freeze",
      "ops.phase.promote_sit":      "Promote to SIT",
      "ops.phase.promote_uat":      "Promote to UAT",
      "ops.phase.promote_prod":     "Promote to PROD",
      "ops.phase.sit_start":        "SIT Start",
      "ops.phase.sit_end":          "SIT Complete",
      "ops.phase.uat_start":        "UAT Start",
      "ops.phase.uat_end":          "UAT Complete",
      "ops.phase.fov_readiness":    "FOV Readiness",
      "ops.phase.fov":              "FOV Review",
      "ops.phase.go_live":          "Go Live",
      "ops.phase.release":          "Release",
      "ops.phase.deploy":           "Deploy",
      "ops.phase.regression":       "Regression Testing",
      "ops.phase.sign_off":         "Sign-Off",
      "ops.phase.approval":         "Approval",
      "ops.phase.kickoff":          "Kickoff",
      "ops.phase.planning":         "Planning",
      "ops.phase.review":           "Review",
      "ops.audience.changelog":     "Changelog",
      "ops.audience.internal":      "Internal",
      "ops.audience.customer":      "Customer-facing",
      "ops.format.markdown":        "Markdown",
      "ops.format.html":            "HTML",
      "ops.cancel":                 "Cancel",
      "ops.cancelled":              "Cancelled",
      "ops.language":               "Language",
      "ops.processing_repo":        "Processing {repo} ({n}/{total})\u2026",
      "ops.tags_pending_analysis":  "Run analysis to update",
      "ops.tags_not_current":       "Data may not be current",
      "ops.no_language_selected":   "No target language selected. Translation service may be unavailable.",
      "ops.invalid_json_input":     "Invalid JSON input \u2014 please check syntax.",
      "ops.translation_failed_prefix": "Translation failed: ",
      "ops.start_rn_tool_hint":     "Start a tool with release notes capability.",
      "ops.errors_label":           "Errors:",
      "ops.cal_header_phase":       "Phase",
      "ops.cal_header_date":        "Date",
      "ops.cal_header_status":      "Status"
    },

    pl: window.__OPS_PL || {}
  };

  /* ================================================================
     i18n Engine
     ================================================================ */

  function getLang() {
    return localStorage.getItem("opsportal_lang") ||
           _detectBrowserLang() ||
           "en";
  }

  function _detectBrowserLang() {
    var nav = (navigator.language || "").slice(0, 2).toLowerCase();
    return T[nav] ? nav : null;
  }

  function t(key, params) {
    var lang = getLang();
    var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]) || key;
    if (params) {
      Object.keys(params).forEach(function (k) {
        val = val.replace(new RegExp("\\{" + k + "\\}", "g"), params[k]);
      });
    }
    return val;
  }

  function tp(key, count) {
    var form = _pluralForm(getLang(), count);
    var resolved = t(key + "." + form) || t(key);
    return resolved.replace(/\{count\}/g, String(count));
  }

  function _pluralForm(lang, n) {
    if (lang === "pl") {
      if (n === 1) return "one";
      var mod10 = n % 10, mod100 = n % 100;
      if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "few";
      return "many";
    }
    return n === 1 ? "one" : "other";
  }

  function formatNumber(n, opts) {
    try { return new Intl.NumberFormat(getLang(), opts || {}).format(n); }
    catch (e) { return String(n); }
  }

  function applyLanguage(lang) {
    localStorage.setItem("opsportal_lang", lang);
    document.cookie = "opsportal_lang=" + lang + ";path=/;max-age=31536000;SameSite=Lax";
    document.documentElement.lang = lang;
    // Standard text content
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]);
      if (val) {
        if (el.hasAttribute("data-i18n-html")) {
          el.innerHTML = val;
        } else {
          el.textContent = val;
        }
      }
    });
    // Title attributes
    document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-title");
      var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]);
      if (val) { el.title = val; el.setAttribute("aria-label", val); }
    });
    // Aria-label only
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-aria");
      var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]);
      if (val) el.setAttribute("aria-label", val);
    });
    // Placeholders
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]);
      if (val) el.placeholder = val;
    });
    // Dynamic content: translate server-rendered values via data-i18n-map
    document.querySelectorAll("[data-i18n-map]").forEach(function (el) {
      var prefix = el.getAttribute("data-i18n-map");
      var raw = el.getAttribute("data-raw") || el.textContent.trim();
      if (!el.getAttribute("data-raw")) el.setAttribute("data-raw", raw);
      var key = prefix + "." + raw.toLowerCase().replace(/[\s_]+/g, "_");
      var val = (T[lang] && T[lang][key]) || (T.en && T.en[key]);
      if (val) el.textContent = val;
    });
    // Document title
    var titleEl = document.querySelector("[data-i18n-doc-title]");
    if (titleEl) {
      var titleKey = titleEl.getAttribute("data-i18n-doc-title");
      var titleVal = (T[lang] && T[lang][titleKey]) || (T.en && T.en[titleKey]);
      if (titleVal) document.title = titleVal;
    }
    updateLangButtons(lang);
    if (typeof broadcastToIframes === 'function') {
      broadcastToIframes({type: 'opsportal:lang', lang: lang});
    }
  }

  function updateLangButtons(lang) {
    document.querySelectorAll("[data-lang-set]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-lang-set") === lang);
    });
  }

  /* ================================================================
     Expose globals
     ================================================================ */

  window.T = T;
  window.t = t;
  window.tp = tp;
  window.formatNumber = formatNumber;
  window.applyLanguage = applyLanguage;
  window.getLang = getLang;

})();
