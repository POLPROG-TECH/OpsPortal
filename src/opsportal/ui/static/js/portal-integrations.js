/* OPSPortal — Operations Overview: refresh, calendar/tags, release notes, translation */
(function () {
  "use strict";

  /* ── Constants ── */
  var DASHBOARD_API_URL     = '/api/integrations/dashboard?refresh=1';
  var RELEASE_NOTES_STREAM_URL = '/api/integrations/release-notes/stream';
  var TRANSLATE_STREAM_URL  = '/api/integrations/translate/stream';
  var TRANSLATE_LANGUAGES_URL = '/api/integrations/translate/languages';
  var MAX_MILESTONES_TIMELINE = 10, MAX_MILESTONES_TABLE = 8, MAX_TAGS_DISPLAY = 8;
  var CAL_VIEW_STORAGE_KEY  = 'opsportal_cal_view';

  /* ── State ── */
  var _cachedCsrfToken = '', _refreshTimers = {}, _dashboardMeta = {};
  var _lastReleaseNotesMd = '', _lastTranslatedJson = null;
  var _serviceStatus = {}, _rnAbortController = null;

  /* ── Utilities ── */
  function _getCsrf() {
    if (!_cachedCsrfToken) {
      var m = document.cookie.match(/opsportal_csrf=([^;]+)/);
      _cachedCsrfToken = m ? m[1] : '';
    }
    return _cachedCsrfToken;
  }
  function _escapeHtml(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(String(s)));
    return d.innerHTML;
  }
  function _downloadFile(name, content, mime) {
    var blob = new Blob([content], { type: mime });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  }
  function _spinner(text) { return '<div class="ops-loading-bar"><span class="ops-spinner"></span> ' + _escapeHtml(text) + '</div>'; }
  function _spinnerLarge(text) { return '<div class="ops-loading-bar"><span class="ops-spinner ops-spinner-large"></span> ' + _escapeHtml(text) + '</div>'; }
  function _toolPageLink(slug, label) { return '<a href="/tools/' + _escapeHtml(slug) + '">' + _escapeHtml(label) + '</a>'; }
  function _toggleWidget(id, show) { var el = document.getElementById(id); if (el) el.classList.toggle('u-hidden', !show); }
  function _findToolWithCapability(cap) {
    var caps = (_dashboardMeta || {}).capabilities || {};
    var tools = Object.keys(caps);
    for (var i = 0; i < tools.length; i++) { if (caps[tools[i]].indexOf(cap) >= 0) return tools[i]; }
    return null;
  }

  /* ── SSE Stream Helper ── */
  function _readSSEStream(response, onEvent, onDone) {
    var reader = response.body.getReader(), decoder = new TextDecoder(), buffer = '';
    function pump() {
      return reader.read().then(function (chunk) {
        if (chunk.done) { if (onDone) onDone(); return; }
        buffer += decoder.decode(chunk.value, { stream: true });
        var lines = buffer.split('\n'); buffer = lines.pop() || '';
        lines.forEach(function (line) {
          if (line.indexOf('data: ') === 0) {
            try { onEvent(JSON.parse(line.substring(6))); } catch (e) { /* skip malformed */ }
          }
        });
        return pump();
      });
    }
    return pump();
  }

  /* ── Dashboard Data Loading ── */
  function refreshOpsOverview() {
    var calBody = document.getElementById('widget-calendar-body');
    var tagsBody = document.getElementById('widget-tags-body');
    if (calBody) { calBody.innerHTML = ''; calBody.classList.add('ops-widget-skeleton'); }
    if (tagsBody) { tagsBody.innerHTML = ''; tagsBody.classList.add('ops-widget-skeleton'); }
    fetch(DASHBOARD_API_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (calBody) calBody.classList.remove('ops-widget-skeleton');
        if (tagsBody) tagsBody.classList.remove('ops-widget-skeleton');
        _dashboardMeta = data;
        _serviceStatus = _buildServiceStatus(data);
        renderCalendarWidget(data.calendar || {});
        renderTagsWidget(data.tags || {});
        updateWidgetVisibility(data);
        setupAutoRefresh(data.widgets || []);
      })
      .catch(function () {
        if (calBody) calBody.classList.remove('ops-widget-skeleton');
        if (tagsBody) tagsBody.classList.remove('ops-widget-skeleton');
        _showWidgetFetchError('widget-calendar-body', 'calendar');
        _showWidgetFetchError('widget-tags-body', 'tags');
      });
  }
  function _buildServiceStatus(data) {
    var caps = data.capabilities || {}, status = {};
    Object.keys(caps).forEach(function (tool) { status[tool] = { available: true, capabilities: caps[tool] }; });
    return status;
  }
  function _showWidgetFetchError(elementId, widgetName) {
    var el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = '<div class="ops-widget-error">'
      + _escapeHtml(t('ops.could_not_load', {name: widgetName})) + ' '
      + '<a href="#" onclick="refreshOpsOverview(); return false;">' + _escapeHtml(t('ops.retry')) + '</a></div>';
  }
  function updateWidgetVisibility(data) {
    var caps = data.capabilities || {};
    var hasCal  = Object.keys(caps).some(function (k) { return caps[k].indexOf('release_calendar') >= 0; });
    var hasTags = Object.keys(caps).some(function (k) { return caps[k].indexOf('tags') >= 0; });
    var hasRN   = Object.keys(caps).some(function (k) { return caps[k].indexOf('release_notes') >= 0; });
    var hasTr   = Object.keys(caps).some(function (k) { return caps[k].indexOf('translation') >= 0; });
    _toggleWidget('widget-calendar', hasCal);
    _toggleWidget('widget-tags', hasTags);
    var rnBtn = document.querySelector('[onclick="openReleaseNotes()"]');
    var trBtn = document.querySelector('[onclick="openTranslateJson()"]');
    if (rnBtn) rnBtn.classList.toggle('u-hidden', !hasRN);
    if (trBtn) trBtn.classList.toggle('u-hidden', !hasTr);
  }
  function setupAutoRefresh(widgets) {
    Object.keys(_refreshTimers).forEach(function (k) { clearInterval(_refreshTimers[k]); });
    _refreshTimers = {};
    widgets.forEach(function (w) {
      if (w.refresh_seconds > 0 && w.available) {
        _refreshTimers[w.id] = setInterval(function () {
          if (document.hidden) return;
          refreshOpsOverview();
        }, w.refresh_seconds * 1000);
      }
    });
  }
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden && document.getElementById('ops-overview')) { refreshOpsOverview(); }
  });

  /* ── Calendar Widget ── */
  function _urgencyClass(days) {
    if (days <= 0) return ' class="ops-phase-past"';
    if (days <= 3) return ' class="ops-phase-urgent"';
    if (days <= 7) return ' class="ops-phase-warn"';
    return ' class="ops-phase-ok"';
  }
  var _PHASE_ICONS = {
    feature_freeze: '❄️', code_freeze: '🧊', freeze: '❄️',
    promote: '🚀', promote_sit: '🚀', promote_uat: '🚀', promote_prod: '🚀',
    sit_start: '🧪', sit_end: '✅', sit: '🧪',
    uat_start: '🧪', uat_end: '✅', uat: '🧪',
    fov: '🔍', fov_readiness: '🔍', readiness: '🔍',
    release: '🎉', go_live: '🎉', deploy: '📦',
    regression: '🔄', sign_off: '✍️', approval: '✍️',
    kickoff: '🏁', planning: '📋', review: '📝'
  };
  function _phaseIcon(phase) {
    if (!phase) return '📅';
    var key = phase.toLowerCase().replace(/[\s-]+/g, '_');
    if (_PHASE_ICONS[key]) return _PHASE_ICONS[key];
    for (var k in _PHASE_ICONS) { if (key.indexOf(k) >= 0) return _PHASE_ICONS[k]; }
    return '📅';
  }
  function _phaseLabel(phase) {
    if (!phase) return '';
    var key = phase.toLowerCase().replace(/[\s-]+/g, '_'), val = t('ops.phase.' + key);
    return val !== 'ops.phase.' + key ? val : phase.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }
  function _daysLabel(d) {
    if (d === 0) return '<span class="ops-badge ops-badge-now">' + _escapeHtml(t('ops.days_today')) + '</span>';
    if (d < 0) return '<span class="ops-badge ops-badge-past">' + _escapeHtml(t('ops.days_ago', {n: Math.abs(d)})) + '</span>';
    var cls = d <= 3 ? 'ops-badge-urgent' : (d <= 7 ? 'ops-badge-warn' : 'ops-badge-ok');
    return '<span class="ops-badge ' + cls + '">' + _escapeHtml(t('ops.days_in', {n: d})) + '</span>';
  }
  function _getCalView() { return localStorage.getItem(CAL_VIEW_STORAGE_KEY) || 'timeline'; }
  function toggleCalendarView() {
    var next = _getCalView() === 'timeline' ? 'table' : 'timeline';
    localStorage.setItem(CAL_VIEW_STORAGE_KEY, next);
    if (_dashboardMeta && _dashboardMeta.calendar) renderCalendarWidget(_dashboardMeta.calendar);
  }
  function renderCalendarWidget(cal) {
    var el = document.getElementById('widget-calendar-body');
    if (!el) return;
    var milestones = cal.milestones || [];
    var errors = cal.errors || [];
    if (milestones.length === 0 && errors.length > 0) {
      var src = errors[0].tool || 'releaseboard';
      el.innerHTML = '<div class="ops-widget-prompt"><span class="ops-spinner"></span><br>'
        + _toolPageLink(src, t('ops.start_tool', {tool: src})) + ' ' + _escapeHtml(t('ops.to_load_calendar')) + '</div>';
      return;
    }
    if (milestones.length === 0) {
      var calTool = _findToolWithCapability('release_calendar');
      var hint = calTool
        ? '<div class="ops-widget-link">' + _toolPageLink(calTool, t('ops.open_releaseboard_calendar')) + '</div>'
        : '';
      el.innerHTML = '<div class="ops-widget-empty">' + _escapeHtml(t('ops.no_milestones')) + '</div>' + hint;
      return;
    }
    if (_getCalView() === 'table') { _renderCalendarTable(el, milestones, errors); }
    else { _renderCalendarTimeline(el, milestones, errors); }
  }
  function _renderCalendarTimeline(el, milestones, errors) {
    var ms = milestones.slice(0, MAX_MILESTONES_TIMELINE);
    var dates = ms.map(function (m) { return new Date(m.date).getTime(); });
    var minT = Math.min.apply(null, dates) - 2 * 864e5, maxT = Math.max.apply(null, dates) + 5 * 864e5;
    var span = maxT - minT || 1, now = Date.now();
    var nowPct = Math.max(0, Math.min(100, (now - minT) / span * 100));
    var mHtml = '', md = new Date(minT); md.setDate(1);
    while (md.getTime() <= maxT) {
      var p = Math.max(0, (md.getTime() - minT) / span * 100);
      if (p < 98) mHtml += '<span class="ops-g-mo" style="left:' + p.toFixed(1) + '%">' + md.toLocaleDateString(undefined, {month: 'short'}) + '</span>';
      md.setMonth(md.getMonth() + 1);
    }
    var todayMk = (nowPct > 1 && nowPct < 99) ? '<div class="ops-g-now" style="left:' + nowPct.toFixed(1) + '%"></div>' : '';
    var nowIdx = -1;
    for (var i = 0; i < ms.length; i++) { if (ms[i].days_remaining >= 0) { nowIdx = i; break; } }
    var html = '<div class="ops-gantt">'
      + '<div class="ops-g-row ops-g-head"><div class="ops-g-lbl"></div><div class="ops-g-trk">' + mHtml + todayMk + '</div></div>';
    ms.forEach(function (m, i) {
      var t0 = dates[i], t1 = i < ms.length - 1 ? dates[i + 1] : t0 + 3 * 864e5;
      var lp = ((t0 - minT) / span * 100).toFixed(1);
      var wp = Math.max(2, (t1 - t0) / span * 100).toFixed(1);
      var bc = i === nowIdx ? 'ops-g-bar ops-g-act' : (m.days_remaining < 0 ? 'ops-g-bar ops-g-done' : 'ops-g-bar');
      html += '<div class="ops-g-row"><div class="ops-g-lbl" title="' + _escapeHtml(m.date) + '">'
        + _phaseIcon(m.phase || m.label) + '<span>' + _escapeHtml(_phaseLabel(m.label || m.phase)) + '</span></div>'
        + '<div class="ops-g-trk">' + todayMk
        + '<div class="' + bc + '" style="left:' + lp + '%;width:' + wp + '%">'
        + '<span class="ops-g-dt">' + _escapeHtml(m.date.slice(5)) + '</span></div></div></div>';
    });
    html += '</div>' + _calendarFooter(milestones, errors);
    el.innerHTML = html;
  }
  function _renderCalendarTable(el, milestones, errors) {
    var html = '<table class="ops-mini-table"><thead><tr>'
      + '<th>' + _escapeHtml(t('ops.cal_header_phase')) + '</th>'
      + '<th>' + _escapeHtml(t('ops.cal_header_date')) + '</th>'
      + '<th>' + _escapeHtml(t('ops.cal_header_status')) + '</th>'
      + '</tr></thead><tbody>';
    milestones.slice(0, MAX_MILESTONES_TABLE).forEach(function (m) {
      html += '<tr><td>' + _escapeHtml(_phaseLabel(m.label || m.phase)) + '</td><td>' + _escapeHtml(m.date) + '</td><td>' + _daysLabel(m.days_remaining) + '</td></tr>';
    });
    html += '</tbody></table>' + _calendarFooter(milestones, errors);
    el.innerHTML = html;
  }
  function _calendarFooter(milestones, errors) {
    var html = '';
    if (milestones[0] && milestones[0].source) html += '<div class="ops-widget-link"><a href="/tools/' + _escapeHtml(milestones[0].source) + '">' + _escapeHtml(t('ops.view_full_calendar')) + '</a></div>';
    if (errors.length > 0) html += '<div class="ops-widget-warn">' + _escapeHtml(t('ops.sources_unavailable', {n: errors.length})) + '</div>';
    return html;
  }

  /* ── Tags Widget ── */
  function renderTagsWidget(tags) {
    var el = document.getElementById('widget-tags-body');
    if (!el) return;
    var items = tags.tags || [];
    var errors = tags.errors || [];
    if (items.length === 0 && errors.length > 0) {
      var src = errors[0].tool || 'releaseboard';
      var errMsg = (errors[0].error || '').toLowerCase();
      var isNoData = errMsg.indexOf('no_data') >= 0 || errMsg.indexOf('no analysis') >= 0 || errMsg.indexOf('404') >= 0;
      if (isNoData) {
        el.innerHTML = '<div class="ops-widget-empty">📊 ' + _escapeHtml(t('ops.no_analysis')) + '</div>'
          + '<div class="ops-widget-link">' + _toolPageLink(src, t('ops.open_releaseboard_analysis', {tool: src})) + '</div>';
      } else {
        el.innerHTML = '<div class="ops-widget-prompt"><span class="ops-spinner"></span><br>'
          + _toolPageLink(src, t('ops.start_tool', {tool: src})) + ' ' + _escapeHtml(t('ops.to_see_tags')) + '</div>';
      }
      return;
    }
    if (items.length === 0) {
      var tagTool = _findToolWithCapability('tags');
      var hint = tagTool
        ? '<div class="ops-widget-link">' + _toolPageLink(tagTool, t('ops.open_releaseboard_analysis', {tool: 'ReleaseBoard'})) + '</div>'
        : '';
      el.innerHTML = '<div class="ops-widget-empty">' + _escapeHtml(t('ops.no_tags')) + '</div>' + hint;
      return;
    }
    var html = '<div class="ops-tag-list">';
    items.slice(0, MAX_TAGS_DISPLAY).forEach(function (tg) {
      var tagName = tg.tag_name || '', date = tg.committed_date ? tg.committed_date.substring(0, 10) : '';
      var repo = tg.repo_name || '', hasTag = !!tagName, age = _tagAge(date);
      html += '<div class="ops-tag-row"><div class="ops-tag-repo">'
        + '<span class="ops-tag-repo-icon">📦</span><span class="ops-tag-repo-name">' + _escapeHtml(repo) + '</span>'
        + '</div><div class="ops-tag-info">';
      if (hasTag) {
        html += '<span class="ops-tag-label">🏷️ ' + _escapeHtml(tagName) + '</span>';
        if (date) html += '<span class="ops-tag-date">' + _escapeHtml(date) + age + '</span>';
      } else if (tg.pending_analysis) {
        html += '<span class="ops-tag-none">⏳ ' + _escapeHtml(t('ops.tags_pending_analysis')) + '</span>';
      } else {
        html += '<span class="ops-tag-none">' + _escapeHtml(t('ops.tag_no_tags')) + '</span>';
      }
      html += '</div></div>';
    });
    html += '</div>';
    var hasPending = items.some(function (i) { return i.pending_analysis; });
    if (hasPending) { html += '<div class="ops-widget-warn ops-tags-warn">⚠ ' + _escapeHtml(t('ops.tags_not_current')) + '</div>'; }
    if (items[0] && items[0].source) {
      html += '<div class="ops-widget-link"><a href="/tools/' + _escapeHtml(items[0].source) + '">' + _escapeHtml(t('ops.view_in_releaseboard')) + '</a></div>';
    }
    if (tags.total > MAX_TAGS_DISPLAY) { html += '<div class="ops-widget-more">' + _escapeHtml(t('ops.more_items', {n: tags.total - MAX_TAGS_DISPLAY})) + '</div>'; }
    el.innerHTML = html;
  }

  function _tagAge(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr), now = new Date(), days = Math.floor((now - d) / 86400000);
    if (days <= 0) return ' <span class="ops-badge ops-badge-ok">' + _escapeHtml(t('ops.tag_today')) + '</span>';
    var cls = days <= 7 ? 'ops-badge-ok' : (days <= 30 ? 'ops-badge-warn' : 'ops-badge-past');
    return ' <span class="ops-badge ' + cls + '">' + _escapeHtml(t('ops.days_ago', {n: days})) + '</span>';
  }

  /* ── Release Notes ── */
  function openReleaseNotes() {
    document.getElementById('release-notes-modal').classList.remove('u-hidden');
    document.getElementById('rn-result').classList.add('u-hidden');
    _lastReleaseNotesMd = '';
    var rnTool = _findToolWithCapability('release_notes'), hint = document.getElementById('rn-service-hint');
    if (hint) {
      hint.innerHTML = rnTool
        ? '<span class="ops-service-badge ops-service-badge-ok">● ' + _escapeHtml(t('ops.connected')) + '</span>'
        : '<span class="ops-service-badge ops-service-badge-down">● ' + _escapeHtml(t('ops.no_tools_available')) + '</span>';
    }
  }
  function closeModal(id) { document.getElementById(id).classList.add('u-hidden'); }
  function cancelReleaseNotes() {
    if (_rnAbortController) { _rnAbortController.abort(); _rnAbortController = null; }
    var generateBtn = document.getElementById('rn-generate-btn');
    var cancelBtn = document.getElementById('rn-cancel-btn');
    if (generateBtn) { generateBtn.disabled = false; generateBtn.textContent = t('ops.generate'); }
    if (cancelBtn) cancelBtn.classList.add('u-hidden');
    var resultEl = document.getElementById('rn-result');
    if (resultEl) resultEl.innerHTML = '<div class="ops-widget-warn">' + _escapeHtml(t('ops.cancelled')) + '</div>';
  }
  function _rnDone(generateBtn, cancelBtn) {
    generateBtn.disabled = false; generateBtn.textContent = t('ops.generate');
    if (cancelBtn) cancelBtn.classList.add('u-hidden'); _rnAbortController = null;
  }
  function _renderRnResults(data) {
    var summary = data.summary || {}, allMd = '';
    var html = '<div class="ops-success">' + _escapeHtml(t('ops.generated_summary', {succeeded: summary.succeeded, total: summary.total_repos, apps: summary.total_apps})) + '</div>';
    if (summary.total_repos === 0 && summary.total_apps === 0) {
      var rnTool = _findToolWithCapability('release_notes');
      html += '<div class="ops-widget-prompt ops-rn-prompt">'
        + _escapeHtml(t('ops.no_repos')) + ' '
        + (rnTool ? _toolPageLink(rnTool, t('ops.open_tool_config')) : _escapeHtml(t('ops.start_rn_tool_hint')))
        + '</div>';
    }
    (data.results || []).forEach(function (app) { (app.repos || []).forEach(function (repo) {
      if (repo.success && repo.content) {
        allMd += '## ' + repo.repo_name + '\n\n' + repo.content + '\n\n';
        html += '<details class="ops-rn-detail"><summary>' + _escapeHtml(repo.repo_name) + ' (' + (repo.total_changes || 0) + ' changes)</summary><pre class="ops-rn-content">' + _escapeHtml(repo.content) + '</pre></details>';
      } else if (!repo.success && repo.error_message) {
        html += '<details class="ops-rn-detail"><summary class="ops-rn-error-summary">✗ ' + _escapeHtml(repo.repo_name) + '</summary><div class="ops-error ops-rn-error-detail">' + _escapeHtml(repo.error_message) + '</div></details>';
      }
    }); });
    _lastReleaseNotesMd = allMd;
    if (allMd) html += '<div class="ops-export-bar"><button type="button" class="btn btn-sm btn-ghost" onclick="downloadReleaseNotes()">⬇ ' + _escapeHtml(t('ops.download_json').replace('JSON','md')) + '</button><button type="button" class="btn btn-sm btn-ghost" onclick="copyReleaseNotes()">📋 ' + _escapeHtml(t('ops.copy_clipboard')) + '</button></div>';
    if ((data.errors || []).length > 0) {
      html += '<div class="ops-widget-warn">' + _escapeHtml(t('ops.errors_label')) + '<ul class="ops-error-list">';
      data.errors.forEach(function (e) {
        var em = _escapeHtml(e.error), lk = '';
        if (em.indexOf('run analysis first') >= 0 || em.indexOf('No analysis') >= 0) lk = ' — ' + _toolPageLink(e.app, t('ops.open_releaseboard_analysis', {tool: e.app}));
        else if (em.indexOf('not available') >= 0 || em.indexOf('Cannot reach') >= 0) lk = ' — ' + _toolPageLink(e.app, t('ops.start_tool', {tool: e.app}));
        html += '<li>' + _escapeHtml(e.app) + ': ' + em + lk + '</li>';
      });
      html += '</ul></div>';
    }
    return html;
  }
  function _setupRnStreamUI(generateBtn, cancelBtn, resultEl) {
    generateBtn.disabled = true;
    generateBtn.textContent = t('ops.generating');
    if (cancelBtn) cancelBtn.classList.remove('u-hidden');
    resultEl.classList.remove('u-hidden');
    resultEl.innerHTML = _spinnerLarge(t('ops.generating'))
      + '<div class="ops-progress-wrap"><div class="ops-progress-bar ops-progress-bar-zero" id="rn-progress-bar"></div></div>'
      + '<div class="ops-progress-text" id="rn-progress-text"></div>';
  }
  function generateReleaseNotes() {
    var generateBtn = document.getElementById('rn-generate-btn');
    var cancelBtn = document.getElementById('rn-cancel-btn');
    var resultEl = document.getElementById('rn-result');
    var langEl = document.getElementById('rn-language');
    _setupRnStreamUI(generateBtn, cancelBtn, resultEl);
    _rnAbortController = new AbortController();
    fetch(RELEASE_NOTES_STREAM_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _getCsrf()},
      body: JSON.stringify({ audience: document.getElementById('rn-audience').value, output_format: document.getElementById('rn-format').value, language: langEl ? langEl.value : 'en' }),
      signal: _rnAbortController.signal
    }).then(function (response) {
      if (!response.ok) return response.json().then(function (d) { _rnDone(generateBtn, cancelBtn); resultEl.innerHTML = '<div class="ops-error">' + _escapeHtml(d.error || t('ops.generation_failed')) + '</div>'; });

      return _readSSEStream(response, function (evt) {
        if (evt.type === 'progress') {
          var bar = document.getElementById('rn-progress-bar');
          var progressText = document.getElementById('rn-progress-text');
          if (bar) bar.style.width = evt.progress + '%';
          if (progressText) progressText.textContent = t('ops.processing_repo', {repo: evt.current_repo, n: evt.processed, total: evt.total});
        } else if (evt.type === 'complete') {
          _rnDone(generateBtn, cancelBtn);
          resultEl.innerHTML = _renderRnResults(evt);
        }
      }, function () {
        _rnDone(generateBtn, cancelBtn);
      });
    }).catch(function (err) {
      _rnDone(generateBtn, cancelBtn);
      resultEl.innerHTML = err.name === 'AbortError'
        ? '<div class="ops-widget-warn">' + _escapeHtml(t('ops.cancelled')) + '</div>'
        : '<div class="ops-error">' + _escapeHtml(t('ops.error_prefix')) + ' ' + _escapeHtml(err.message) + '</div>';
    });
  }
  function downloadReleaseNotes() {
    if (_lastReleaseNotesMd) _downloadFile('release-notes.md', _lastReleaseNotesMd, 'text/markdown');
  }
  function copyReleaseNotes() {
    if (!_lastReleaseNotesMd) return;
    navigator.clipboard.writeText(_lastReleaseNotesMd).then(function () {
      var copyBtn = document.querySelector('[onclick="copyReleaseNotes()"]');
      if (copyBtn) { copyBtn.textContent = '✓ ' + t('ops.copied'); setTimeout(function () { copyBtn.textContent = '📋 ' + t('ops.copy_clipboard'); }, 1500); }
    });
  }

  /* ── JSON Translation ── */
  function openTranslateJson() {
    var modal = document.getElementById('translate-modal');
    modal.classList.remove('u-hidden');
    document.getElementById('tr-result').classList.add('u-hidden');
    var trTool = _findToolWithCapability('translation'), hint = document.getElementById('tr-service-hint');
    if (hint) {
      hint.innerHTML = trTool
        ? '<span class="ops-service-badge ops-service-badge-ok">● ' + _escapeHtml(t('ops.connected')) + '</span>'
        : '<span class="ops-service-badge ops-service-badge-down">● ' + _escapeHtml(t('ops.service_unavailable')) + '</span>';
    }
    var sel = document.getElementById('tr-language');
    if (sel.options.length <= 1) {
      sel.innerHTML = '<option value="">' + _escapeHtml(t('ops.loading_languages')) + '</option>';
      fetch(TRANSLATE_LANGUAGES_URL)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          sel.innerHTML = '';
          var langs = data.languages || [];
          if (langs.length === 0) {
            sel.innerHTML = '<option value="">' + _escapeHtml(t('ops.no_languages')) + '</option>';
            return;
          }
          langs.forEach(function (lang) {
            var opt = document.createElement('option');
            opt.value = lang.code;
            opt.textContent = lang.label + ' (' + lang.code + ')';
            sel.appendChild(opt);
          });
        })
        .catch(function () {
          sel.innerHTML = '<option value="">' + _escapeHtml(t('ops.languages_failed')) + '</option>';
          var resultEl = document.getElementById('tr-result');
          resultEl.classList.remove('u-hidden');
          resultEl.innerHTML = '<div class="ops-widget-error">' + _escapeHtml(t('ops.translation_unavailable')) + '</div>';
        });
    }
  }
  function handleJsonFile(input) {
    var file = input.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function (e) { document.getElementById('tr-input').value = e.target.result; };
    reader.readAsText(file);
  }
  function _validateTranslationInput(input, lang, resultEl) {
    if (!lang) {
      resultEl.classList.remove('u-hidden');
      resultEl.innerHTML = '<div class="ops-error">' + _escapeHtml(t('ops.no_language_selected')) + '</div>';
      return null;
    }
    try {
      return JSON.parse(input);
    } catch (e) {
      resultEl.classList.remove('u-hidden');
      resultEl.innerHTML = '<div class="ops-error">' + _escapeHtml(t('ops.invalid_json_input')) + '</div>';
      return null;
    }
  }
  function _setupTranslateStreamUI(translateBtn, resultEl, keyCount, langLabel) {
    translateBtn.disabled = true;
    translateBtn.textContent = t('ops.translating', {keys: keyCount, lang: langLabel});
    resultEl.classList.remove('u-hidden');
    resultEl.innerHTML = '<div class="ops-loading-bar"><span class="ops-spinner ops-spinner-large"></span> '
      + _escapeHtml(t('ops.translating', {keys: keyCount, lang: langLabel})) + '</div>'
      + '<div class="ops-progress-wrap"><div class="ops-progress-bar ops-progress-bar-zero" id="tr-progress-bar"></div></div>'
      + '<div class="ops-progress-text" id="tr-progress-text">0 / ' + keyCount + ' keys (0%)</div>';
  }
  function translateJson() {
    var translateBtn = document.getElementById('tr-translate-btn');
    var resultEl = document.getElementById('tr-result');
    var input = document.getElementById('tr-input').value.trim();
    var lang = document.getElementById('tr-language').value;
    var parsed = _validateTranslationInput(input, lang, resultEl);
    if (!parsed) return;
    var keyCount = _countJsonKeys(parsed);
    var langSelect = document.getElementById('tr-language');
    var langLabel = langSelect.selectedOptions[0] ? langSelect.selectedOptions[0].textContent : lang;
    _setupTranslateStreamUI(translateBtn, resultEl, keyCount, langLabel);
    fetch(TRANSLATE_STREAM_URL, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': _getCsrf()},
      body: JSON.stringify({ json_data: parsed, target_language: lang })
    }).then(function (response) {
      if (!response.ok) {
        return response.json().then(function (data) {
          translateBtn.disabled = false; translateBtn.textContent = t('ops.translate');
          resultEl.innerHTML = '<div class="ops-error">' + _escapeHtml(data.error || t('ops.generation_failed')) + '</div>';
        });
      }
      return _readSSEStream(response, function (evt) {
        if (evt.complete) {
          _handleTranslationComplete(evt, resultEl, translateBtn);
        } else if (evt.progress !== undefined) {
          _updateTranslationProgress(evt);
        }
      }, function () {
        translateBtn.disabled = false;
        translateBtn.textContent = t('ops.translate');
      });
    }).catch(function (err) {
      translateBtn.disabled = false; translateBtn.textContent = t('ops.translate');
      resultEl.innerHTML = '<div class="ops-error">' + _escapeHtml(t('ops.translation_failed_prefix')) + ' ' + _escapeHtml(err.message) + '</div>';
    });
  }
  function _updateTranslationProgress(evt) {
    var bar = document.getElementById('tr-progress-bar');
    var text = document.getElementById('tr-progress-text');
    if (bar) bar.style.width = evt.progress + '%';
    if (text) text.textContent = evt.done + ' / ' + evt.total + ' keys (' + evt.progress + '%)';
  }
  function _handleTranslationComplete(evt, resultEl, translateBtn) {
    translateBtn.disabled = false; translateBtn.textContent = t('ops.translate');
    if (!evt.ok) {
      var errHtml = '<div class="ops-error">' + _escapeHtml(evt.error) + '</div>';
      if ((evt.error || '').indexOf('not installed') >= 0) errHtml += '<div class="ops-action-hint">' + _escapeHtml(t('ops.translation_unavailable')) + '</div>';
      resultEl.innerHTML = errHtml; return;
    }
    _lastTranslatedJson = evt.translated_json;
    resultEl.innerHTML = '<div class="ops-success">✓ ' + _escapeHtml(t('ops.translation_complete')) + ' (' + evt.keys_translated + '/' + evt.keys_skipped + ')</div>'
      + '<pre class="ops-rn-content">' + _escapeHtml(JSON.stringify(evt.translated_json, null, 2)) + '</pre>'
      + '<div class="ops-export-bar"><button type="button" class="btn btn-sm btn-ghost" onclick="downloadTranslatedJson()">⬇ ' + _escapeHtml(t('ops.download_json')) + '</button></div>';
  }
  function _countJsonKeys(obj) {
    var count = 0;
    function walk(o) {
      if (o && typeof o === 'object' && !Array.isArray(o)) {
        Object.keys(o).forEach(function (k) {
          if (typeof o[k] === 'string') count++;
          else walk(o[k]);
        });
      }
    }
    walk(obj);
    return count;
  }
  function downloadTranslatedJson() {
    if (!_lastTranslatedJson) return;
    var lang = document.getElementById('tr-language').value || 'translated';
    _downloadFile('translated-' + lang + '.json', JSON.stringify(_lastTranslatedJson, null, 2), 'application/json');
  }

  /* ── Initialization ── */
  (function _initDropZone() {
    var dz = document.getElementById('tr-dropzone');
    if (!dz) return;
    dz.addEventListener('dragover', function (e) { e.preventDefault(); dz.classList.add('ops-drop-active'); });
    dz.addEventListener('dragleave', function () { dz.classList.remove('ops-drop-active'); });
    dz.addEventListener('drop', function (e) {
      e.preventDefault(); dz.classList.remove('ops-drop-active');
      var file = e.dataTransfer.files[0];
      if (file && file.name.endsWith('.json')) {
        var reader = new FileReader();
        reader.onload = function (ev) { document.getElementById('tr-input').value = ev.target.result; };
        reader.readAsText(file);
      }
    });
  })();
  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('ops-overview')) { refreshOpsOverview(); }
  });

  /* ── Expose Globals ── */
  window.refreshOpsOverview = refreshOpsOverview;
  window.toggleCalendarView = toggleCalendarView;
  window.openReleaseNotes = openReleaseNotes;
  window.openTranslateJson = openTranslateJson;
  window.closeModal = closeModal;
  window.cancelReleaseNotes = cancelReleaseNotes;
  window.generateReleaseNotes = generateReleaseNotes;
  window.downloadReleaseNotes = downloadReleaseNotes;
  window.copyReleaseNotes = copyReleaseNotes;
  window.handleJsonFile = handleJsonFile;
  window.translateJson = translateJson;
  window.downloadTranslatedJson = downloadTranslatedJson;
})();
