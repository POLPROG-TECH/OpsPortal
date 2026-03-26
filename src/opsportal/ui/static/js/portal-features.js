/**
 * Fullscreen mode, bulk actions, drag-and-drop card reorder,
 * breadcrumb navigation history, and SSE log streaming.
 *
 * Depends on: portal.js (exposes showToast, showModal, _csrfToken),
 *             portal-i18n.js (exposes t()).
 */
(function () {
  "use strict";

  /* ================================================================
     Fullscreen Mode (#6)
     ================================================================ */

  function toggleFullscreen() {
    var wrapper = document.getElementById('iframe-wrapper');
    if (!wrapper) return;
    var header = document.querySelector('.header');
    var breadcrumb = document.querySelector('.breadcrumb-bar');
    var controls = document.querySelector('.tool-header');
    var iframeControls = document.querySelector('.iframe-controls');
    var footer = document.querySelector('.app-footer');
    var isFullscreen = wrapper.classList.toggle('iframe-fullscreen');

    if (header) header.style.display = isFullscreen ? 'none' : '';
    if (breadcrumb) breadcrumb.style.display = isFullscreen ? 'none' : '';
    if (controls) controls.style.display = isFullscreen ? 'none' : '';
    if (iframeControls) iframeControls.style.display = isFullscreen ? 'none' : '';
    if (footer) footer.style.display = isFullscreen ? 'none' : '';

    var btn = document.getElementById('fullscreen-btn');
    if (btn) {
      var label = btn.querySelector('span');
      if (label) label.textContent = isFullscreen ? t('tool.exit_fullscreen') : t('tool.fullscreen');
    }

    var fab = document.getElementById('fullscreen-exit-fab');
    if (fab) fab.style.display = isFullscreen ? '' : 'none';
  }

  // Exit fullscreen with Escape key
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var wrapper = document.getElementById('iframe-wrapper');
      if (wrapper && wrapper.classList.contains('iframe-fullscreen')) {
        toggleFullscreen();
      }
    }
  });

  /* ================================================================
     Bulk Actions (#4)
     ================================================================ */

  function bulkAction(actionName) {
    var confirmMsg = actionName === 'stop'
      ? t('bulk.confirm_stop')
      : t('bulk.confirm_action').replace('{action}', actionName);

    window.showModal({
      title: t('bulk.title'),
      message: confirmMsg,
      confirmLabel: t('modal.confirm'),
      cancelLabel: t('modal.cancel'),
      danger: actionName === 'stop',
    }).then(function (confirmed) {
      if (!confirmed) return;
      window.showToast(t('bulk.running').replace('{action}', actionName), 'info');
      _executeBulk(actionName);
    });
  }

  function _executeBulk(actionName) {
    fetch('/api/tools/bulk/' + actionName, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window._csrfToken() },
    })
      .then(function (res) { return res.json(); })
      .then(function (data) { _handleBulkResult(data, actionName); })
      .catch(function (err) {
        window.showToast(t('action.request_failed') + err.message, 'error');
      });
  }

  function _handleBulkResult(data, actionName) {
    if (data.error) {
      window.showToast(data.error, 'error');
      return;
    }
    if (!data.results) {
      window.showToast(t('action.request_failed') + 'Unexpected response', 'error');
      return;
    }
    var total = Object.keys(data.results).length;
    var succeeded = Object.values(data.results).filter(function(r) { return r.success; }).length;
    var level = succeeded === total ? 'success' : 'error';
    window.showToast(
      t('bulk.completed').replace('{n}', succeeded).replace('{total}', total), level
    );
    setTimeout(function() { location.reload(); }, 1500);
  }

  /* ================================================================
     Drag & Drop Card Reorder (#5)
     ================================================================ */

  function initDragAndDrop() {
    var grid = document.getElementById('product-grid');
    if (!grid) return;

    var draggedEl = null;

    grid.addEventListener('dragstart', function (e) {
      var card = e.target.closest('.product-card');
      if (!card) return;
      draggedEl = card;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.getAttribute('data-slug'));
    });

    grid.addEventListener('dragend', function () {
      if (draggedEl) {
        draggedEl.classList.remove('dragging');
        draggedEl = null;
      }
      grid.querySelectorAll('.product-card').forEach(function(c) {
        c.classList.remove('drag-over');
      });
    });

    grid.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      var target = e.target.closest('.product-card');
      if (target && target !== draggedEl) {
        grid.querySelectorAll('.product-card').forEach(function(c) { c.classList.remove('drag-over'); });
        target.classList.add('drag-over');
      }
    });

    grid.addEventListener('drop', function (e) {
      e.preventDefault();
      var target = e.target.closest('.product-card');
      if (!target || !draggedEl || target === draggedEl) return;

      var allCards = Array.from(grid.querySelectorAll('.product-card'));
      var draggedIdx = allCards.indexOf(draggedEl);
      var targetIdx = allCards.indexOf(target);

      if (draggedIdx < targetIdx) {
        grid.insertBefore(draggedEl, target.nextSibling);
      } else {
        grid.insertBefore(draggedEl, target);
      }

      var newOrder = Array.from(grid.querySelectorAll('.product-card')).map(function(c) {
        return c.getAttribute('data-slug');
      });
      try { localStorage.setItem('opsportal_card_order', JSON.stringify(newOrder)); } catch(ignore) {}
    });

    _restoreCardOrder(grid);
  }

  function _restoreCardOrder(grid) {
    try {
      var saved = JSON.parse(localStorage.getItem('opsportal_card_order') || '[]');
      if (!saved.length) return;
      var cards = {};
      grid.querySelectorAll('.product-card').forEach(function(c) {
        cards[c.getAttribute('data-slug')] = c;
      });
      saved.forEach(function(slug) {
        if (cards[slug]) grid.appendChild(cards[slug]);
      });
    } catch(ignore) {}
  }

  /* ================================================================
     Breadcrumb Navigation History (#7)
     ================================================================ */

  function initBreadcrumbHistory() {
    var current = window.location.pathname;
    try {
      var history = JSON.parse(sessionStorage.getItem('opsportal_nav_history') || '[]');
      if (history[history.length - 1] !== current) {
        history.push(current);
        if (history.length > 20) history = history.slice(-20);
        sessionStorage.setItem('opsportal_nav_history', JSON.stringify(history));
      }
    } catch(ignore) {}
  }

  /* ================================================================
     SSE Log Streaming (#2)
     ================================================================ */

  function initLogStreaming() {
    var logArea = document.querySelector('.output-area');
    var toolSlug = _getToolSlugFromPath();
    if (logArea && toolSlug) {
      _startLogStream('/api/tools/' + toolSlug + '/logs/stream', logArea);
    }
  }

  function _getToolSlugFromPath() {
    var match = window.location.pathname.match(/^\/tools\/([^/]+)$/);
    return match ? match[1] : null;
  }

  function _startLogStream(url, container) {
    if (!window.EventSource) return;
    var source = new EventSource(url);
    source.onmessage = function(e) {
      try {
        var data = JSON.parse(e.data);
        var line = document.createElement('div');
        line.className = 'log-stream-line';
        line.textContent = data.line;
        container.appendChild(line);
        container.scrollTop = container.scrollHeight;
      } catch(err) {}
    };
    source.onerror = function() {
      setTimeout(function() { _startLogStream(url, container); }, 5000);
      source.close();
    };
    window.addEventListener('beforeunload', function() { source.close(); });
  }

  /* ================================================================
     Initialization
     ================================================================ */

  document.addEventListener("DOMContentLoaded", function () {
    initDragAndDrop();
    initBreadcrumbHistory();
    initLogStreaming();
  });

  /* ================================================================
     Expose Globals
     ================================================================ */

  window.toggleFullscreen = toggleFullscreen;
  window.bulkAction = bulkAction;
})();
