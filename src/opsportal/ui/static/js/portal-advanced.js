/**
 * OpsPortal – Advanced UI Features
 *
 * Sidebar navigation, Command Palette (⌘K), Dark/Light theme auto-schedule,
 * Activity feed real-time stream, Dependency graph helpers.
 */
(function () {
  "use strict";

  var MAX_PALETTE_RESULTS = 12;
  var MAX_FEED_ITEMS = 50;
  var FEED_RECONNECT_DELAY_MS = 5000;
  var MAX_FEED_RETRIES = 5;
  var THEME_CHECK_INTERVAL_MS = 300000;

  /* ================================================================
     Collapsible Left Sidebar
     ================================================================ */

  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("sidebar-backdrop");
  var sidebarToggle = document.getElementById("sidebar-toggle");

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("open");
    backdrop.classList.add("open");
    sidebarToggle.setAttribute("aria-expanded", "true");
  }
  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    backdrop.classList.remove("open");
    sidebarToggle.setAttribute("aria-expanded", "false");
  }
  if (sidebarToggle) {
    sidebarToggle.addEventListener("click", function () {
      var isOpen = sidebar.classList.contains("open");
      if (isOpen) { closeSidebar(); } else { openSidebar(); }
    });
  }
  if (backdrop) {
    backdrop.addEventListener("click", closeSidebar);
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sidebar && sidebar.classList.contains("open")) {
      closeSidebar();
    }
  });

  /* ================================================================
     Command Palette (⌘K / Ctrl+K)
     ================================================================ */

  var _allItems = [
    { type: "page", label: t('nav.home'), url: "/", icon: "🏠" },
    { type: "page", label: t('nav.dashboard'), url: "/dashboard", icon: "📊" },
    { type: "page", label: t('nav.health'), url: "/health", icon: "💊" },
    { type: "page", label: t('nav.uptime'), url: "/uptime", icon: "📈" },
    { type: "page", label: t('nav.logs'), url: "/logs", icon: "📋" },
    { type: "page", label: t('nav.config'), url: "/config", icon: "⚙️" },
    { type: "page", label: t('nav.sla'), url: "/sla", icon: "📑" },
  ];

  var _selectedIndex = 0;
  var _filteredItems = [];

  function openPalette() {
    var overlay = document.getElementById("cmd-palette");
    if (!overlay) return;

    // Dynamically add tool items
    loadToolItems(function () {
      overlay.classList.remove("u-hidden");
      var input = document.getElementById("cmd-palette-input");
      input.value = "";
      input.focus();
      filterPalette("");
    });
  }

  function closePalette() {
    var overlay = document.getElementById("cmd-palette");
    if (overlay) overlay.classList.add("u-hidden");
  }

  function loadToolItems(callback) {
    // Only load once
    if (_allItems.length > 10) { callback(); return; }
    fetch("/api/tools")
      .then(function (r) { return r.json(); })
      .then(function (tools) {
        tools.forEach(function (tool) {
          _allItems.push(
            { type: "tool", label: tool.name, url: "/tools/" + tool.slug, icon: "🔧" },
            { type: "action", label: t('cmd.start_tool', {name: tool.name}), url: "/tools/" + tool.slug, action: "start", slug: tool.slug, icon: "▶️" },
            { type: "action", label: t('cmd.stop_tool', {name: tool.name}), url: "/tools/" + tool.slug, action: "stop", slug: tool.slug, icon: "⏹️" }
          );
        });
        callback();
      })
      .catch(function () { callback(); });
  }

  function filterPalette(query) {
    var lowerQuery = query.toLowerCase();
    _filteredItems = _allItems.filter(function (item) {
      return !lowerQuery || item.label.toLowerCase().indexOf(lowerQuery) !== -1 || item.type.indexOf(lowerQuery) !== -1;
    });
    _selectedIndex = 0;
    renderPaletteResults();
  }

  function renderPaletteResults() {
    var container = document.getElementById("cmd-palette-results");
    if (!container) return;
    var html = _filteredItems.slice(0, MAX_PALETTE_RESULTS).map(function (item, idx) {
      var cls = "cmd-palette-item" + (idx === _selectedIndex ? " cmd-palette-active" : "");
      return '<div class="' + cls + '" data-idx="' + idx + '">' +
        '<span class="cmd-palette-icon">' + item.icon + '</span>' +
        '<span class="cmd-palette-label">' + item.label + '</span>' +
        '<span class="cmd-palette-type">' + item.type + '</span>' +
        '</div>';
    }).join("");
    container.innerHTML = html || '<div class="cmd-palette-empty">' + t('cmd.no_results') + '</div>';
  }

  function executePaletteItem(item) {
    closePalette();
    if (item.action && item.slug && window._csrfToken) {
      fetch("/api/tools/" + item.slug + "/actions/" + item.action, {
        method: "POST",
        headers: { "X-CSRF-Token": window._csrfToken() },
      }).then(function () {
        if (window.showToast) window.showToast(t('cmd.action_executed', {label: item.label}), "success");
      }).catch(function () {
        if (window.showToast) window.showToast(t('cmd.action_failed', {label: item.label}), "error");
      });
    } else {
      window.location.href = item.url;
    }
  }

  document.addEventListener("keydown", function (e) {
    var overlay = document.getElementById("cmd-palette");
    if (!overlay) return;

    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      overlay.classList.contains("u-hidden") ? openPalette() : closePalette();
      return;
    }

    if (overlay.classList.contains("u-hidden")) return;

    if (e.key === "Escape") { closePalette(); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      _selectedIndex = Math.min(_selectedIndex + 1, _filteredItems.length - 1);
      renderPaletteResults();
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      _selectedIndex = Math.max(_selectedIndex - 1, 0);
      renderPaletteResults();
    }
    if (e.key === "Enter" && _filteredItems[_selectedIndex]) {
      e.preventDefault();
      executePaletteItem(_filteredItems[_selectedIndex]);
    }
  });

  var _paletteInput = document.getElementById("cmd-palette-input");
  if (_paletteInput) {
    _paletteInput.addEventListener("input", function () { filterPalette(this.value); });
  }

  var _paletteOverlay = document.getElementById("cmd-palette");
  if (_paletteOverlay) {
    _paletteOverlay.addEventListener("click", function (e) {
      if (e.target === _paletteOverlay) closePalette();
      var item = e.target.closest(".cmd-palette-item");
      if (item) {
        var idx = parseInt(item.getAttribute("data-idx"), 10);
        if (_filteredItems[idx]) executePaletteItem(_filteredItems[idx]);
      }
    });
  }

  /* ================================================================
     Dark/Light Theme Auto-Schedule
     ================================================================ */

  function checkThemeSchedule() {
    var schedule = null;
    try { schedule = JSON.parse(localStorage.getItem("opsportal_theme_schedule")); } catch (ignore) {}
    if (!schedule || !schedule.enabled) return;

    var hour = new Date().getHours();
    var isDayTime = hour >= (schedule.light_start || 7) && hour < (schedule.dark_start || 20);
    var targetTheme = isDayTime ? "light" : "dark";
    var currentTheme = document.documentElement.getAttribute("data-theme");

    if (currentTheme !== targetTheme && schedule.auto_applied !== targetTheme) {
      if (window.applyTheme) window.applyTheme(targetTheme);
      schedule.auto_applied = targetTheme;
      try { localStorage.setItem("opsportal_theme_schedule", JSON.stringify(schedule)); } catch (ignore) {}
    }
  }

  function setThemeSchedule(enabled, lightStart, darkStart) {
    var schedule = { enabled: enabled, light_start: lightStart || 7, dark_start: darkStart || 20, auto_applied: "" };
    try { localStorage.setItem("opsportal_theme_schedule", JSON.stringify(schedule)); } catch (ignore) {}
    if (enabled) checkThemeSchedule();
  }

  // Check theme schedule on load and every 5 minutes
  checkThemeSchedule();
  setInterval(checkThemeSchedule, THEME_CHECK_INTERVAL_MS);

  /* ================================================================
     Activity Feed (real-time SSE on home page)
     ================================================================ */

  var _feedRetries = 0;

  function initActivityFeed() {
    var feed = document.getElementById("activity-feed");
    if (!feed || !window.EventSource) return;

    var source = new EventSource("/api/logs/stream");
    source.onmessage = function (e) {
      _feedRetries = 0;
      try {
        var data = JSON.parse(e.data);
        var item = document.createElement("div");
        item.className = "feed-item feed-level-" + (data.level || "info");

        var time = document.createElement("span");
        time.className = "feed-time";
        time.textContent = data.time;

        var tool = document.createElement("span");
        tool.className = "feed-tool";
        tool.textContent = data.tool || "portal";

        var msg = document.createElement("span");
        msg.className = "feed-message";
        msg.textContent = data.message;

        item.appendChild(time);
        item.appendChild(tool);
        item.appendChild(msg);
        feed.insertBefore(item, feed.firstChild);

        while (feed.children.length > MAX_FEED_ITEMS) {
          feed.removeChild(feed.lastChild);
        }
      } catch (ignore) {}
    };

    source.onerror = function () {
      source.close();
      if (_feedRetries < MAX_FEED_RETRIES) {
        _feedRetries++;
        setTimeout(initActivityFeed, FEED_RECONNECT_DELAY_MS);
      }
    };

    window.addEventListener("beforeunload", function () { source.close(); });
  }

  document.addEventListener("DOMContentLoaded", initActivityFeed);

  /* ================================================================
     Expose Globals
     ================================================================ */

  window.openCommandPalette = openPalette;
  window.setThemeSchedule = setThemeSchedule;
})();
