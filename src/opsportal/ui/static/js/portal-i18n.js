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
      "nav.dashboard":              "Dashboard",
      "nav.health":                 "Health",
      "nav.logs":                   "Logs",
      "nav.settings":               "Settings",

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

      /* ---------- status dots ---------- */
      "status.error":               "Error",
      "status.needs_config":        "Needs configuration",
      "status.ready":               "Ready to launch",
      "status.running":             "Running",

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


      /* ---------- status badges ---------- */
      "status.running":             "Running",
      "status.stopped":             "Stopped",
      "status.starting":            "Starting",
      "status.error":               "Error",
      "status.idle":                "Idle",
      "status.ready":               "Ready",
      "status.needs_config":        "Needs configuration",
      "status.not_running":         "Not running",

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
      "config.saved":               "Configuration saved",
      "config.dir_required":        "Directory is required",
      "config.source_required":     "Source locale is required",
      "config.invalid_locale":      "Invalid locale code",
      "config.unknown_property":    "Unknown property",

      /* ---------- error defaults ---------- */
      "error.unexpected":           "An unexpected error occurred.",
      "error.tool_not_found":       "Tool not found",
      "error.action_not_supported": "Action not supported",

      /* ---------- page titles (document.title) ---------- */
      "page.title.home":            "OpsPortal — Engineering Operations Platform",
      "page.title.health":          "Health — OpsPortal",
      "page.title.logs":            "Logs — OpsPortal",
      "page.title.config":          "Configuration — OpsPortal",
      "page.title.error":           "Error — OpsPortal",

      /* ---------- aria / accessibility ---------- */
      "aria.main_nav":              "Main navigation",
      "aria.activity_log":          "Activity log",
      "aria.portal_settings":       "Portal settings",
      "aria.registered_tools":      "Registered tools",
      "aria.raw_json_config":       "Raw JSON configuration",

      /* ---------- units ---------- */
      "unit.kb":                    "KB",
      "unit.ms":                    "ms"
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
