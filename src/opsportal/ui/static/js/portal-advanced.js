/**
 * OpsPortal – Advanced UI Features
 *
 * Sidebar navigation, Command Palette (⌘K), Dark/Light theme auto-schedule,
 * Activity feed real-time stream, Dependency graph helpers.
 */
(function () {
  "use strict";

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

  var paletteItems = [
    { type: "page", label: "Home", url: "/", icon: "🏠" },
    { type: "page", label: "Dashboard", url: "/dashboard", icon: "📊" },
    { type: "page", label: "Health", url: "/health", icon: "💊" },
    { type: "page", label: "Uptime", url: "/uptime", icon: "📈" },
    { type: "page", label: "Logs", url: "/logs", icon: "📋" },
    { type: "page", label: "Config", url: "/config", icon: "⚙️" },
    { type: "page", label: "SLA Report", url: "/sla", icon: "📑" },
  ];

  var paletteSelectedIdx = 0;
  var paletteFiltered = [];

  function openPalette() {
    var overlay = document.getElementById("cmd-palette");
    if (!overlay) return;

    // Dynamically add tool items
    loadToolItems(function () {
      overlay.style.display = "";
      var input = document.getElementById("cmd-palette-input");
      input.value = "";
      input.focus();
      filterPalette("");
    });
  }

  function closePalette() {
    var overlay = document.getElementById("cmd-palette");
    if (overlay) overlay.style.display = "none";
  }

  function loadToolItems(callback) {
    // Only load once
    if (paletteItems.length > 10) { callback(); return; }
    fetch("/api/tools")
      .then(function (r) { return r.json(); })
      .then(function (tools) {
        tools.forEach(function (t) {
          paletteItems.push(
            { type: "tool", label: t.name, url: "/tools/" + t.slug, icon: "🔧" },
            { type: "action", label: "Start " + t.name, url: "/tools/" + t.slug, action: "start", slug: t.slug, icon: "▶️" },
            { type: "action", label: "Stop " + t.name, url: "/tools/" + t.slug, action: "stop", slug: t.slug, icon: "⏹️" }
          );
        });
        callback();
      })
      .catch(function () { callback(); });
  }

  function filterPalette(query) {
    var q = query.toLowerCase();
    paletteFiltered = paletteItems.filter(function (item) {
      return !q || item.label.toLowerCase().indexOf(q) !== -1 || item.type.indexOf(q) !== -1;
    });
    paletteSelectedIdx = 0;
    renderPaletteResults();
  }

  function renderPaletteResults() {
    var container = document.getElementById("cmd-palette-results");
    if (!container) return;
    var html = paletteFiltered.slice(0, 12).map(function (item, idx) {
      var cls = "cmd-palette-item" + (idx === paletteSelectedIdx ? " cmd-palette-active" : "");
      return '<div class="' + cls + '" data-idx="' + idx + '">' +
        '<span class="cmd-palette-icon">' + item.icon + '</span>' +
        '<span class="cmd-palette-label">' + item.label + '</span>' +
        '<span class="cmd-palette-type">' + item.type + '</span>' +
        '</div>';
    }).join("");
    container.innerHTML = html || '<div class="cmd-palette-empty">No results</div>';
  }

  function executePaletteItem(item) {
    closePalette();
    if (item.action && item.slug && window._csrfToken) {
      fetch("/api/tools/" + item.slug + "/actions/" + item.action, {
        method: "POST",
        headers: { "X-CSRF-Token": window._csrfToken() },
      }).then(function () {
        if (window.showToast) window.showToast(item.label + " executed", "success");
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
      overlay.style.display === "none" ? openPalette() : closePalette();
      return;
    }

    if (overlay.style.display === "none") return;

    if (e.key === "Escape") { closePalette(); return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteSelectedIdx = Math.min(paletteSelectedIdx + 1, paletteFiltered.length - 1);
      renderPaletteResults();
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteSelectedIdx = Math.max(paletteSelectedIdx - 1, 0);
      renderPaletteResults();
    }
    if (e.key === "Enter" && paletteFiltered[paletteSelectedIdx]) {
      e.preventDefault();
      executePaletteItem(paletteFiltered[paletteSelectedIdx]);
    }
  });

  var cmdInput = document.getElementById("cmd-palette-input");
  if (cmdInput) {
    cmdInput.addEventListener("input", function () { filterPalette(this.value); });
  }

  var cmdOverlay = document.getElementById("cmd-palette");
  if (cmdOverlay) {
    cmdOverlay.addEventListener("click", function (e) {
      if (e.target === cmdOverlay) closePalette();
      var item = e.target.closest(".cmd-palette-item");
      if (item) {
        var idx = parseInt(item.getAttribute("data-idx"), 10);
        if (paletteFiltered[idx]) executePaletteItem(paletteFiltered[idx]);
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
  setInterval(checkThemeSchedule, 300000);

  /* ================================================================
     Activity Feed (real-time SSE on home page)
     ================================================================ */

  function initActivityFeed() {
    var feed = document.getElementById("activity-feed");
    if (!feed || !window.EventSource) return;

    var source = new EventSource("/api/logs/stream");
    source.onmessage = function (e) {
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

        // Keep max 50 items
        while (feed.children.length > 50) {
          feed.removeChild(feed.lastChild);
        }
      } catch (ignore) {}
    };

    source.onerror = function () {
      source.close();
      setTimeout(initActivityFeed, 5000);
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
