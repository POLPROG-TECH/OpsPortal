/* ============================================================
   OpsPortal — Portal Interactions
   Theme, Gear Menu, Modal, Toast, Lifecycle
   ============================================================ */

(function () {
  "use strict";

  /* ================================================================
     CSRF Token Helper
     ================================================================ */

  function _csrfToken() {
    var m = document.cookie.match(/opsportal_csrf=([^;]+)/);
    return m ? m[1] : "";
  }

  /* ================================================================
     Broadcast to child iframes (theme / language inheritance)
     ================================================================ */

  function broadcastToIframes(msg) {
    var frames = document.querySelectorAll('iframe.tool-iframe');
    frames.forEach(function(f) {
      try { f.contentWindow.postMessage(msg, '*'); } catch(e) { /* cross-origin ok */ }
    });
  }

  /* ================================================================
     Theme Engine
     ================================================================ */

  function getThemePref() {
    return localStorage.getItem("opsportal_theme") || "system";
  }

  function resolveTheme(pref) {
    if (pref === "system") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return pref;
  }

  function applyTheme(pref) {
    localStorage.setItem("opsportal_theme", pref);
    var resolved = resolveTheme(pref);
    document.documentElement.setAttribute("data-theme", resolved);
    updateThemeButtons(pref);
    broadcastToIframes({type: "opsportal:theme", theme: resolved});
  }

  function updateThemeButtons(pref) {
    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.classList.toggle("active", btn.getAttribute("data-theme-set") === pref);
    });
  }

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
    if (getThemePref() === "system") {
      applyTheme("system");
    }
  });

  /* ================================================================
     Gear Menu (with keyboard navigation)
     ================================================================ */

  function initGearMenu() {
    var toggle = document.getElementById("gear-toggle");
    var dropdown = document.getElementById("gear-dropdown");
    if (!toggle || !dropdown) return;

    function openDropdown() {
      dropdown.classList.add("open");
      toggle.setAttribute("aria-expanded", "true");
      var first = dropdown.querySelector("button, a");
      if (first) first.focus();
    }

    function closeDropdown() {
      dropdown.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.focus();
    }

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      if (dropdown.classList.contains("open")) {
        closeDropdown();
      } else {
        openDropdown();
      }
    });

    toggle.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        if (!dropdown.classList.contains("open")) {
          e.preventDefault();
          openDropdown();
        }
      }
    });

    dropdown.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeDropdown();
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        var items = Array.from(dropdown.querySelectorAll("button[role='menuitem'], a[role='menuitem']"));
        var idx = items.indexOf(document.activeElement);
        if (e.key === "ArrowDown") idx = (idx + 1) % items.length;
        else idx = (idx - 1 + items.length) % items.length;
        items[idx].focus();
      }
    });

    document.addEventListener("click", function (e) {
      if (!dropdown.contains(e.target) && e.target !== toggle) {
        dropdown.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });

    dropdown.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyTheme(btn.getAttribute("data-theme-set"));
      });
    });

    dropdown.querySelectorAll("[data-lang-set]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyLanguage(btn.getAttribute("data-lang-set"));
      });
    });
  }

  /* ================================================================
     Custom Modal (with focus trap and focus restore)
     ================================================================ */

  var modalResolve = null;
  var modalTrigger = null;

  function trapFocus(e, focusable) {
    if (e.key !== "Tab") return;
    e.preventDefault();
    var idx = focusable.indexOf(document.activeElement);
    var delta = e.shiftKey ? -1 : 1;
    var next = (idx + delta + focusable.length) % focusable.length;
    focusable[next].focus();
  }

  function showModal(opts) {
    var overlay = document.getElementById("modal-overlay");
    var titleEl = document.getElementById("modal-title");
    var msgEl = document.getElementById("modal-message");
    var confirmBtn = document.getElementById("modal-confirm");
    var cancelBtn = document.getElementById("modal-cancel");
    var closeBtn = document.getElementById("modal-close-x");

    modalTrigger = document.activeElement;

    titleEl.textContent = opts.title || t("modal.dangerous.title");
    msgEl.textContent = opts.message || t("modal.dangerous.message");
    confirmBtn.textContent = opts.confirmLabel || t("modal.confirm");
    cancelBtn.textContent = opts.cancelLabel || t("modal.cancel");
    confirmBtn.className = "btn " + (opts.danger !== false ? "btn-danger" : "btn-primary");

    overlay.classList.add("open");
    cancelBtn.focus();

    return new Promise(function (resolve) {
      modalResolve = resolve;
      var focusable = [closeBtn, cancelBtn, confirmBtn];

      function cleanup() {
        overlay.classList.remove("open");
        confirmBtn.removeEventListener("click", onConfirm);
        cancelBtn.removeEventListener("click", onCancel);
        closeBtn.removeEventListener("click", onCancel);
        document.removeEventListener("keydown", onKey);
        modalResolve = null;
        if (modalTrigger && modalTrigger.focus) { modalTrigger.focus(); }
        modalTrigger = null;
      }

      function onConfirm() { cleanup(); resolve(true); }
      function onCancel() { cleanup(); resolve(false); }
      function onKey(e) {
        if (e.key === "Escape") { e.preventDefault(); onCancel(); return; }
        trapFocus(e, focusable);
      }

      confirmBtn.addEventListener("click", onConfirm);
      cancelBtn.addEventListener("click", onCancel);
      closeBtn.addEventListener("click", onCancel);
      document.addEventListener("keydown", onKey);
    });
  }

  /* ================================================================
     Toast Notifications
     ================================================================ */

  function showToast(message, type) {
    type = type || "info";
    var container = document.getElementById("toast-container");
    if (!container) return;

    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function () {
      toast.style.animation = "toast-out 0.3s ease forwards";
      setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
  }

  /* ================================================================
     Loading State
     ================================================================ */

  function setLoading(button, loading) {
    if (!button) return;
    if (loading) {
      button.dataset.originalText = button.textContent;
      button.textContent = "";
      var spinner = document.createElement("span");
      spinner.className = "spinner";
      button.appendChild(spinner);
      button.appendChild(document.createTextNode(" " + t("action.running")));
      button.classList.add("loading");
      button.disabled = true;
    } else {
      button.textContent = button.dataset.originalText || button.textContent;
      button.classList.remove("loading");
      button.disabled = false;
    }
  }

  /* ================================================================
     Translatable Action Name Helper
     ================================================================ */

  function _tAction(name) {
    var key = "action.name." + name.toLowerCase().replace(/\s+/g, "_");
    var val = t(key);
    return val !== key ? val : name;
  }

  /* ================================================================
     Collect Form Data
     ================================================================ */

  function collectFormData(actionName) {
    var form = document.getElementById("form-" + actionName);
    if (!form) return {};
    var data = {};
    var elements = form.elements;
    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      if (!el.name) continue;
      data[el.name] = el.type === "checkbox" ? (el.checked ? "true" : "false") : el.value;
    }
    return data;
  }

  /* ================================================================
     Resolve Button from Event
     ================================================================ */

  function resolveButton(e) {
    if (!e) return null;
    var el = e.target || e.srcElement;
    if (!el) return null;
    return el.closest ? el.closest("button") : el;
  }

  /* ================================================================
     Output Panel
     ================================================================ */

  function appendOutput(actionLabel, result) {
    var area = document.getElementById("output-area");
    if (!area) return;

    var placeholder = area.querySelector(".output-placeholder");
    if (placeholder) placeholder.remove();

    var entry = document.createElement("div");
    entry.className = "output-entry";

    var header = document.createElement("div");
    header.className = "output-entry-header";
    header.textContent = "[" + new Date().toLocaleTimeString() + "] " + actionLabel;
    entry.appendChild(header);

    var body = document.createElement("div");
    body.className = result.success ? "output-entry-success" : "output-entry-error";
    body.textContent = (result.success ? result.output : result.error) || (result.success ? t("action.completed_ok") : t("action.failed"));
    entry.appendChild(body);

    if (result.duration_ms) {
      var dur = document.createElement("div");
      dur.className = "output-entry-header";
      dur.textContent = t("action.completed_in") + result.duration_ms + t("unit.ms");
      entry.appendChild(dur);
    }

    if (result.artifact) {
      var link = document.createElement("div");
      var a = document.createElement("a");
      a.href = result.artifact;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.style.cssText = "color:var(--primary)";
      a.textContent = t("action.view_artifact");
      link.textContent = "\u21b3 ";
      link.appendChild(a);
      entry.appendChild(link);
    }

    area.insertBefore(entry, area.firstChild);
    area.scrollTop = 0;
  }

  function clearOutput() {
    var area = document.getElementById("output-area");
    if (!area) return;
    area.textContent = "";
    var span = document.createElement("span");
    span.className = "output-placeholder";
    span.textContent = t("cli.output_placeholder");
    area.appendChild(span);
  }

  /* ================================================================
     API Calls (explicit event parameter for cross-browser safety)
     ================================================================ */

  function runAction(slug, actionName, e) {
    var button = resolveButton(e || window.event);
    var params = collectFormData(actionName);
    setLoading(button, true);

    fetch("/api/tools/" + slug + "/actions/" + actionName, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": _csrfToken() },
      body: JSON.stringify(params),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        appendOutput(actionName, data);
        showToast(
          data.success
            ? _tAction(actionName) + t("action.completed_toast")
            : _tAction(actionName) + t("action.failed_toast") + (data.error || t("action.unknown_error")),
          data.success ? "success" : "error"
        );
      })
      .catch(function (err) {
        appendOutput(actionName, { success: false, error: t("action.network_error") + err.message });
        showToast(t("action.request_failed") + err.message, "error");
      })
      .finally(function () {
        setLoading(button, false);
      });
  }

  function runLifecycle(slug, actionName, e) {
    var button = resolveButton(e || window.event);

    if (actionName === "stop") {
      showModal({
        title: t("modal.stop.title"),
        message: t("modal.stop.message"),
        confirmLabel: t("modal.confirm"),
        cancelLabel: t("modal.cancel"),
        danger: true,
      }).then(function (confirmed) {
        if (confirmed) doLifecycle(slug, actionName, button);
      });
      return;
    }

    doLifecycle(slug, actionName, button);
  }

  function doLifecycle(slug, actionName, button) {
    setLoading(button, true);
    showToast(t("action.running_toast") + _tAction(actionName) + "\u2026", "info");

    fetch("/api/tools/" + slug + "/" + actionName, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": _csrfToken() },
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.success) {
          showToast(_tAction(actionName).charAt(0).toUpperCase() + _tAction(actionName).slice(1) + t("action.completed_toast"), "success");
          setTimeout(function () { location.reload(); }, 1000);
        } else {
          showToast(_tAction(actionName) + t("action.failed_toast") + (data.error || t("action.unknown_error")), "error");
        }
      })
      .catch(function (err) {
        showToast(t("action.request_failed") + err.message, "error");
      })
      .finally(function () {
        setLoading(button, false);
      });
  }

  /* ================================================================
     Dangerous Action Confirmation (non-lifecycle)
     ================================================================ */

  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".action-dangerous .btn-danger");
    if (btn && !btn.dataset.confirmed) {
      e.preventDefault();
      e.stopPropagation();
      showModal({
        title: t("modal.dangerous.title"),
        message: t("modal.dangerous.message"),
        confirmLabel: t("modal.confirm"),
        cancelLabel: t("modal.cancel"),
        danger: true,
      }).then(function (confirmed) {
        if (confirmed) {
          btn.dataset.confirmed = "1";
          btn.click();
          delete btn.dataset.confirmed;
        }
      });
    }
  });

  /* ================================================================
     Initialization
     ================================================================ */

  document.addEventListener("DOMContentLoaded", function () {
    initGearMenu();
    applyTheme(getThemePref());
    applyLanguage(getLang());
  });

  /* ================================================================
     Expose Globals
     ================================================================ */

  window.runAction = runAction;
  window.runLifecycle = runLifecycle;
  window.clearOutput = clearOutput;
  window.showToast = showToast;
  window.showModal = showModal;
  window._csrfToken = _csrfToken;
  window.broadcastToIframes = broadcastToIframes;
})();
