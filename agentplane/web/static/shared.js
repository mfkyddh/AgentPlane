// AgentPlane — Shared utilities
// Common helpers used across all view components.
// Loaded BEFORE component scripts in index.html.

// ── Auth headers helper ──
function getAuthHeaders(authToken) {
  const headers = {};
  if (authToken && authToken.value) {
    headers['Authorization'] = `Bearer ${authToken.value}`;
  }
  return headers;
}

// ── Authenticated fetch wrapper with timeout ──
function apiFetch(url, authToken, options) {
  var opts = Object.assign({}, options);
  opts.headers = Object.assign({}, opts.headers, getAuthHeaders(authToken));
  if (!opts.signal) {
    var controller = new AbortController();
    opts.signal = controller.signal;
    setTimeout(function () { controller.abort(); }, opts._timeout || 10000);
  }
  return fetch(url, opts);
}

// ── Time formatting ──
function formatTimestamp(ts) {
  if (!ts) return '-';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function formatRelativeTime(ts, t) {
  if (!ts) return '-';
  try {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now - d;
    if (diffMs < 0) return t('time.just_now');
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('time.just_now');
    if (diffMin < 60) return `${diffMin}${t('time.min_ago')}`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}${t('time.hour_ago')}`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 365) return `${diffDay}${t('time.day_ago')}`;
    const diffYear = Math.floor(diffDay / 365);
    return `${diffYear}y ago`;
  } catch {
    return ts;
  }
}

function formatLogTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return '';
  }
}

// ── Status classification ──
function appStatusClass(status) {
  if (!status) return 'unknown';
  const s = String(status).toLowerCase();
  if (s === 'unknown') return 'unknown';
  if (s.includes('stop') || s.includes('crash') || s.includes('exit') || s.includes('dead') || s.includes('error') || s.includes('fail')) return 'error';
  if (s.includes('deploy') || s.includes('start') || s.includes('building') || s.includes('pending') || s.includes('restart')) return 'unknown';
  if (s.includes('run') || s.includes('active') || s.includes('healthy') || s.includes('online') || s.includes('up') || s.includes('connect')) return 'connected';
  return 'unknown';
}

function serviceStatusClass(status) {
  if (!status) return 'unchecked';
  const s = String(status).toLowerCase();
  if (s.includes('running') || s.includes('active')) return 'connected';
  if (s.includes('error') || s.includes('fail')) return 'error';
  if (s === 'unknown') return 'unchecked';
  return 'unchecked';
}

function resultBadgeClass(result) {
  if (!result) return 'warning';
  const r = String(result).toLowerCase();
  const successWords = ['pass', 'passed', 'verified', 'queried', 'success', 'ok', 'done', 'completed', 'created', 'updated', 'deleted'];
  if (successWords.some(function (s) { return r.includes(s); })) return 'success';
  const failWords = ['fail', 'error', 'timeout', 'refused', 'denied'];
  if (failWords.some(function (s) { return r.includes(s); })) return 'error';
  return 'warning';
}

// ── Detail panel helpers ──
function formatDetailVal(val) {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'object') return JSON.stringify(val, null, 2);
  return String(val);
}

function isDetailUrl(key, val) {
  if (!val || typeof val !== 'string') return false;
  return key === 'public_url' || key === 'url' || key === 'homepage' ||
    (typeof val === 'string' && val.startsWith('https://'));
}

function isDetailStatus(key) {
  return key === 'status' || key === 'result' || key === 'phase_status';
}

function isDetailHidden(key) {
  return key === 'contract_file' || key === '_raw';
}

// ── URL helpers ──
function truncateUrl(url) {
  if (!url) return '';
  try {
    var u = new URL(url);
    return u.hostname + (u.pathname !== '/' ? u.pathname : '');
  } catch {
    return url;
  }
}

// ── Detail panel composable ──
function useDetailPanel(authToken) {
  var detailPanel = Vue.ref({ visible: false, title: '', data: null, loading: false, error: '' });

  function openDetail(title, apiUrl) {
    detailPanel.value = { visible: true, title: title, data: null, loading: true, error: '' };
    return apiFetch(apiUrl, authToken).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function (data) {
      detailPanel.value.data = data;
    }).catch(function (e) {
      detailPanel.value.error = e.message;
    }).finally(function () {
      detailPanel.value.loading = false;
    });
  }

  function closeDetail() {
    detailPanel.value.visible = false;
  }

  function handleEscape(e) {
    if (e.key === 'Escape' && detailPanel.value.visible) closeDetail();
  }

  Vue.onMounted(function () {
    document.addEventListener('keydown', handleEscape);
  });
  Vue.onUnmounted(function () {
    document.removeEventListener('keydown', handleEscape);
  });

  return { detailPanel: detailPanel, openDetail: openDetail, closeDetail: closeDetail };
}

// ── Sortable table composable ──
function useSortable(defaultKey, defaultDir) {
  var sortKey = Vue.ref(defaultKey || '');
  var sortDir = Vue.ref(defaultDir || 'asc');

  function toggleSort(key) {
    if (sortKey.value === key) {
      sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
    } else {
      sortKey.value = key;
      sortDir.value = 'asc';
    }
  }

  function sortIcon(key) {
    if (sortKey.value !== key) return '';
    return sortDir.value === 'asc' ? ' \u25B2' : ' \u25BC';
  }

  function sortAria(key) {
    if (sortKey.value !== key) return 'none';
    return sortDir.value === 'asc' ? 'ascending' : 'descending';
  }

  function sortItems(items, customSort) {
    if (!sortKey.value || !items) return items;
    var dir = sortDir.value === 'asc' ? 1 : -1;
    return items.slice().sort(function (a, b) {
      if (customSort) return customSort(a, b, sortKey.value, dir);
      var va = a[sortKey.value];
      var vb = b[sortKey.value];
      if (va == null) va = '';
      if (vb == null) vb = '';
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  }

  return { sortKey: sortKey, sortDir: sortDir, toggleSort: toggleSort, sortIcon: sortIcon, sortAria: sortAria, sortItems: sortItems };
}

// ── Toast notification system ──
var _toastState = Vue.reactive({ toasts: [] });
var _toastId = 0;
var _lastToast = { message: '', time: 0 };

function showToast(message, type, duration) {
  // Deduplication: skip identical messages within 2 seconds
  var now = Date.now();
  if (message === _lastToast.message && (now - _lastToast.time) < 2000) return;
  _lastToast = { message: message, time: now };

  var id = ++_toastId;
  _toastState.toasts.push({ id: id, message: message, type: type || 'info', duration: duration || 3000 });
  setTimeout(function () {
    var idx = _toastState.toasts.findIndex(function (t) { return t.id === id; });
    if (idx >= 0) _toastState.toasts.splice(idx, 1);
  }, duration || 3000);
}

// ── Copy to clipboard ──
function copyToClipboard(text) {
  if (navigator.clipboard) {
    return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () { return false; });
  }
  return Promise.resolve(false);
}

// ── Debounce helper for search inputs ──
function useDebounce(sourceRef, delay) {
  var debounced = Vue.ref(sourceRef.value);
  var timer = null;
  Vue.watch(sourceRef, function (val) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(function () { debounced.value = val; }, delay || 200);
  });
  Vue.onUnmounted(function () { if (timer) clearTimeout(timer); });
  return debounced;
}

// ── Reusable search filter composable ──
function useSearchFilter(sourceRef, fields, delay) {
  var search = Vue.ref('');
  var debounced = useDebounce(search, delay || 200);
  var filtered = Vue.computed(function () {
    var q = debounced.value.toLowerCase().trim();
    if (!q) return sourceRef.value;
    return sourceRef.value.filter(function (item) {
      return fields.some(function (f) {
        return (item[f] || '').toString().toLowerCase().includes(q);
      });
    });
  });
  return { search: search, filtered: filtered };
}

// ── HTML escaping (used by logs, chat, etc.) ──
function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ── Shared target fetcher (used by operations, logs) ──
function fetchTargetList(authToken) {
  return apiFetch('/api/hosts', authToken).then(function (res) {
    return res.json();
  }).then(function (data) {
    return (data.hosts || []).map(function (h) { return h.target; }).filter(Boolean);
  }).catch(function () { return []; });
}
