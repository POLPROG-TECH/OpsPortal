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
     Constants
     ================================================================ */

  var BULK_RELOAD_DELAY_MS = 2500;
  var MAX_NAV_HISTORY = 20;
  var LOG_RECONNECT_DELAY_MS = 5000;
  var MAX_LOG_RETRIES = 5;
  var STORAGE_KEY_CARD_ORDER = 'opsportal_card_order';
  var STORAGE_KEY_NAV_HISTORY = 'opsportal_nav_history';

  /* ================================================================
     Shared DOM Helpers
     ================================================================ */

  function _clearBadges(nameRow) {
    nameRow.querySelectorAll('.card-status-badge').forEach(function(b) { b.remove(); });
  }

  function _updateStatusDot(card, className, title) {
    var dot = card.querySelector('.status-dot');
    if (dot) { dot.className = 'status-dot ' + className; dot.title = title; }
  }

  function _setCardBadge(card, badgeClass, text, title) {
    var nameRow = card.querySelector('.product-name-row');
    if (!nameRow) return;
    _clearBadges(nameRow);
    var badge = document.createElement('span');
    badge.className = 'card-status-badge ' + badgeClass;
    badge.textContent = text;
    if (title) badge.title = title;
    nameRow.appendChild(badge);
  }

  /* ================================================================
     Fullscreen Mode
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

    if (header) header.classList.toggle('u-hidden', isFullscreen);
    if (breadcrumb) breadcrumb.classList.toggle('u-hidden', isFullscreen);
    if (controls) controls.classList.toggle('u-hidden', isFullscreen);
    if (iframeControls) iframeControls.classList.toggle('u-hidden', isFullscreen);
    if (footer) footer.classList.toggle('u-hidden', isFullscreen);

    var btn = document.getElementById('fullscreen-btn');
    if (btn) {
      var label = btn.querySelector('span');
      if (label) label.textContent = isFullscreen ? t('tool.exit_fullscreen') : t('tool.fullscreen');
    }

    var fab = document.getElementById('fullscreen-exit-fab');
    if (fab) fab.classList.toggle('u-hidden', !isFullscreen);
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var wrapper = document.getElementById('iframe-wrapper');
      if (wrapper && wrapper.classList.contains('iframe-fullscreen')) {
        toggleFullscreen();
      }
    }
  });

  /* ================================================================
     Bulk Actions
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
      _executeBulk(actionName);
    });
  }

  function _prepareBulkCards(cards) {
    cards.forEach(function(card) {
      card.classList.add('product-card-loading');
      _updateStatusDot(card, 'status-idle', t('bulk.waiting'));
      _setCardBadge(card, 'card-status-queued', t('bulk.queued'));
    });
  }

  function _executeBulk(actionName) {
    var cards = document.querySelectorAll('.product-card[data-slug]');
    _prepareBulkCards(cards);

    fetch('/api/tools/bulk/' + actionName, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': (document.cookie.match(/opsportal_csrf=([^;]+)/) || [])[1] || ''
      },
    }).then(function(response) {
      if (!response.ok) {
        return response.text().then(function(body) {
          _clearAllLoadingStates(cards);
          var msg = t('bulk.error_prefix') + response.status;
          try { msg = JSON.parse(body).error || msg; } catch(e) {}
          window.showToast(msg, 'error');
        });
      }
      if (response.body && typeof response.body.getReader === 'function') {
        return _readBulkStream(response, actionName, cards);
      }
      return response.text().then(function(text) {
        _processBulkSSEText(text, actionName, cards);
      });
    }).catch(function(err) {
      _clearAllLoadingStates(cards);
      window.showToast(t('action.request_failed') + (err.message || err), 'error');
    });
  }

  function _readBulkStream(response, actionName, cards) {
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';
    function pump() {
      return reader.read().then(function(chunk) {
        if (chunk.value) {
          buffer += decoder.decode(chunk.value, { stream: true });
          _flushSSEBuffer();
        }
        if (chunk.done) {
          _flushSSEBuffer();
          return;
        }
        return pump();
      });
    }
    function _flushSSEBuffer() {
      var lines = buffer.split('\n');
      buffer = lines.pop() || '';
      lines.forEach(function(line) {
        if (line.indexOf('data: ') !== 0) return;
        try {
          var evt = JSON.parse(line.slice(6));
          _handleBulkStreamEvent(evt, actionName);
        } catch(e) { /* skip malformed SSE line */ }
      });
    }
    return pump().catch(function() {
      if (buffer) _flushSSEBuffer();
      _clearAllLoadingStates(cards);
    });
  }

  function _processBulkSSEText(text, actionName, cards) {
    var lines = text.split('\n');
    lines.forEach(function(line) {
      if (line.indexOf('data: ') !== 0) return;
      try {
        var evt = JSON.parse(line.slice(6));
        _handleBulkStreamEvent(evt, actionName);
      } catch(e) {}
    });
    if (text.indexOf('"phase": "complete"') === -1 && text.indexOf('"phase":"complete"') === -1) {
      _clearAllLoadingStates(cards);
    }
  }

  /* -- Bulk stream event handlers -- */

  function _handleBulkStreamEvent(evt, actionName) {
    if (evt.phase === 'starting') {
      _onBulkStarting(evt, actionName);
    } else if (evt.phase === 'done') {
      _onBulkDone(evt, actionName);
    } else if (evt.phase === 'complete') {
      _onBulkComplete(evt, actionName);
    }
  }

  function _onBulkStarting(evt, actionName) {
    var card = document.querySelector('.product-card[data-slug="' + evt.slug + '"]');
    if (!card) return;
    card.classList.add('product-card-active');
    if (!card.querySelector('.product-card-spinner')) {
      var spinner = document.createElement('div');
      spinner.className = 'product-card-spinner';
      card.appendChild(spinner);
    }
    var statusTitle = actionName === 'stop' ? t('bulk.stopping') : t('bulk.starting');
    _updateStatusDot(card, 'status-starting', statusTitle);
    _setCardBadge(card, 'card-status-starting', statusTitle);
    _updateBulkBanner(actionName, evt.index, evt.total, evt.slug);
  }

  function _onBulkDone(evt, actionName) {
    var card = document.querySelector('.product-card[data-slug="' + evt.slug + '"]');
    if (!card) return;
    card.classList.remove('product-card-loading', 'product-card-active');
    var spinner = card.querySelector('.product-card-spinner');
    if (spinner) spinner.remove();

    if (evt.success) {
      var dotClass = actionName === 'stop' ? 'status-idle' : 'status-running';
      var dotTitle = actionName === 'stop' ? t('status.stopped') : t('status.running');
      _updateStatusDot(card, dotClass, dotTitle);
      var badgeText = actionName === 'stop' ? t('status.stopped') : t('status.ready');
      _setCardBadge(card, 'card-status-ok', badgeText);
    } else {
      _updateStatusDot(card, 'status-error', evt.error || t('status.failed'));
      _setCardBadge(card, 'card-status-failed', t('status.failed'), evt.error || '');
    }
  }

  function _onBulkComplete(evt, actionName) {
    document.querySelectorAll('.product-card-loading').forEach(function(c) {
      c.classList.remove('product-card-loading', 'product-card-active');
      var sp = c.querySelector('.product-card-spinner');
      if (sp) sp.remove();
    });
    _removeBulkBanner();
    var level = evt.succeeded === evt.total ? 'success' : 'error';
    var verb = actionName === 'stop' ? t('bulk.tools_stopped') : t('bulk.tools_started');
    window.showToast(evt.succeeded + ' / ' + evt.total + ' ' + verb, level);
    setTimeout(function() { location.reload(); }, BULK_RELOAD_DELAY_MS);
  }

  function _clearAllLoadingStates(cards) {
    cards.forEach(function(card) {
      card.classList.remove('product-card-loading', 'product-card-active');
      var sp = card.querySelector('.product-card-spinner');
      if (sp) sp.remove();
      var nameRow = card.querySelector('.product-name-row');
      if (nameRow) _clearBadges(nameRow);
    });
    _removeBulkBanner();
  }

  function _updateBulkBanner(actionName, index, total, slug) {
    var banner = document.getElementById('bulk-progress-banner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'bulk-progress-banner';
      banner.className = 'bulk-progress-banner';
      var grid = document.getElementById('product-grid');
      if (grid && grid.parentNode) {
        grid.parentNode.insertBefore(banner, grid);
      } else {
        return;
      }
    }
    var progressPercent = Math.round(((index + 1) / total) * 100);
    var verb = actionName === 'stop' ? t('bulk.stopping') : t('bulk.starting');
    banner.innerHTML =
      '<div class="bulk-banner-text">' + verb + ' <strong>' + slug + '</strong> (' + (index + 1) + '/' + total + ')</div>' +
      '<div class="ops-progress-wrap"><div class="ops-progress-bar" style="width:' + progressPercent + '%"></div></div>';
  }

  function _removeBulkBanner() {
    var banner = document.getElementById('bulk-progress-banner');
    if (banner) banner.remove();
  }

  /* ================================================================
     Drag & Drop Card Reorder
     ================================================================ */

  function initDragAndDrop() {
    var grid = document.getElementById('product-grid');
    if (!grid) return;

    var _draggedCard = null;

    grid.addEventListener('dragstart', function (e) {
      var card = e.target.closest('.product-card');
      if (!card) return;
      _draggedCard = card;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.getAttribute('data-slug'));
    });

    grid.addEventListener('dragend', function () {
      if (_draggedCard) {
        _draggedCard.classList.remove('dragging');
        _draggedCard = null;
      }
      grid.querySelectorAll('.product-card').forEach(function(c) {
        c.classList.remove('drag-over');
      });
    });

    grid.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      var target = e.target.closest('.product-card');
      if (target && target !== _draggedCard) {
        grid.querySelectorAll('.product-card').forEach(function(c) { c.classList.remove('drag-over'); });
        target.classList.add('drag-over');
      }
    });

    grid.addEventListener('drop', function (e) {
      e.preventDefault();
      var target = e.target.closest('.product-card');
      if (!target || !_draggedCard || target === _draggedCard) return;

      var allCards = Array.from(grid.querySelectorAll('.product-card'));
      var draggedIdx = allCards.indexOf(_draggedCard);
      var targetIdx = allCards.indexOf(target);

      if (draggedIdx < targetIdx) {
        grid.insertBefore(_draggedCard, target.nextSibling);
      } else {
        grid.insertBefore(_draggedCard, target);
      }

      var newOrder = Array.from(grid.querySelectorAll('.product-card')).map(function(c) {
        return c.getAttribute('data-slug');
      });
      try { localStorage.setItem(STORAGE_KEY_CARD_ORDER, JSON.stringify(newOrder)); } catch(ignore) {}
    });

    _restoreCardOrder(grid);
  }

  function _restoreCardOrder(grid) {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY_CARD_ORDER) || '[]');
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
     Breadcrumb Navigation History
     ================================================================ */

  function initBreadcrumbHistory() {
    var current = window.location.pathname;
    try {
      var history = JSON.parse(sessionStorage.getItem(STORAGE_KEY_NAV_HISTORY) || '[]');
      if (history[history.length - 1] !== current) {
        history.push(current);
        if (history.length > MAX_NAV_HISTORY) history = history.slice(-MAX_NAV_HISTORY);
        sessionStorage.setItem(STORAGE_KEY_NAV_HISTORY, JSON.stringify(history));
      }
    } catch(ignore) {}
  }

  /* ================================================================
     SSE Log Streaming
     ================================================================ */

  var _logStreamRetries = 0;

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
      source.close();
      if (_logStreamRetries < MAX_LOG_RETRIES) {
        _logStreamRetries++;
        setTimeout(function() { _startLogStream(url, container); }, LOG_RECONNECT_DELAY_MS);
      }
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
