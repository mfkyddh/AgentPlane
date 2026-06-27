// AgentPlane — Vue app setup, state management, routing, shared polling
// Loaded AFTER components/*.js, i18n/index.js, and Vue CDN

const { createApp, ref, computed, provide, inject, onMounted, nextTick, onUnmounted } = Vue;

// ── Shared polling ──
const _refreshCallbacks = new Set();

function useDataPoller(refreshFn) {
  onMounted(() => {
    _refreshCallbacks.add(refreshFn);
    refreshFn();
  });
  onUnmounted(() => _refreshCallbacks.delete(refreshFn));
}

// ── Valid view names ──
const VALID_VIEWS = ['dashboard', 'topology', 'capability-map', 'chat', 'operations', 'logs'];

// ── App factory ──
function createAgentPlaneApp() {
  const app = createApp({
    setup() {
      // Initialize view from URL hash
      const hashView = location.hash.replace('#', '');
      const view = ref(VALID_VIEWS.includes(hashView) ? hashView : 'dashboard');
      const sidebarOpen = ref(false);
      const wsDisconnected = ref(false);
      const needsAuth = ref(false);
      const authenticated = ref(false);
      const authToken = ref('');
      const authError = ref('');
      const showShortcuts = ref(false);
      const globalLoading = ref(false);

      // Toast state (bridged from shared.js _toastState)
      const toasts = computed(() => _toastState.toasts);

      // i18n
      const { locale, t, toggleLocale } = useI18n();
      const viewLabel = computed(() => {
        const labels = { dashboard: t('topbar.overview'), topology: t('topbar.topology'), 'capability-map': t('topbar.capabilities'), chat: t('topbar.chat'), operations: t('topbar.operations'), logs: t('topbar.logs') };
        return labels[view.value] || t('topbar.overview');
      });

      const currentView = computed(() => {
        const map = { dashboard: 'dashboard-view', topology: 'topology-view', 'capability-map': 'capability-map-view', chat: 'chat-view', operations: 'operations-view', logs: 'logs-view' };
        return map[view.value] || 'dashboard-view';
      });

      const shortcutList = computed(() => [
        { key: '/', desc: t('shortcuts.search_focus') },
        { key: '?', desc: t('shortcuts.help') },
        { key: 'r', desc: t('action.refresh') },
        { key: '1', desc: t('topbar.overview') },
        { key: '2', desc: t('topbar.topology') },
        { key: '3', desc: t('topbar.capabilities') },
        { key: '4', desc: t('topbar.chat') },
        { key: '5', desc: t('topbar.operations') },
        { key: '6', desc: t('topbar.logs') },
      ]);

      provide('authToken', authToken);
      provide('globalLoading', globalLoading);

      // Allow child components to navigate to a different view
      function navigateToView(viewName) {
        if (VALID_VIEWS.includes(viewName)) {
          view.value = viewName;
        }
      }
      provide('navigateToView', navigateToView);

      // ── URL hash routing ──
      function syncHashToView() {
        const hash = location.hash.replace('#', '');
        if (VALID_VIEWS.includes(hash) && hash !== view.value) {
          view.value = hash;
        }
      }

      // Sync view → URL hash
      Vue.watch(view, (newView) => {
        sidebarOpen.value = false;
        if (location.hash !== '#' + newView) {
          history.pushState(null, '', '#' + newView);
        }
      });

      // Listen for browser back/forward
      window.addEventListener('hashchange', syncHashToView);
      window.addEventListener('popstate', syncHashToView);

      let ws = null;
      let mtimePoller = null;
      let lastMtime = 0;
      let reconnectDelay = 1000;
      const MAX_RECONNECT_DELAY = 30000;

      function startMtimePolling() {
        apiFetch('/api/mtime', authToken).then(res => res.json()).then(data => {
          lastMtime = data.mtime || 0;
        }).catch(() => {});

        mtimePoller = setInterval(async () => {
          try {
            const res = await apiFetch('/api/mtime', authToken);
            const data = await res.json();
            if (data.mtime > lastMtime) {
              lastMtime = data.mtime;
              for (const fn of _refreshCallbacks) fn();
            }
          } catch { /* ignore */ }
        }, 5000);
      }

      function stopMtimePolling() {
        if (mtimePoller) { clearInterval(mtimePoller); mtimePoller = null; }
      }

      // WebSocket
      function connectWs() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${proto}//${location.host}/ws/chat`);

        ws.onopen = () => {
          wsDisconnected.value = false;
          reconnectDelay = 1000;
          if (authToken.value && needsAuth.value && !authenticated.value) {
            ws.send(JSON.stringify({ type: 'auth', token: authToken.value }));
          }
        };

        ws.onmessage = (event) => {
          let msg;
          try { msg = JSON.parse(event.data); } catch { return; }

          if (msg.type === 'auth_required') {
            if (!authenticated.value) {
              needsAuth.value = true;
              if (authToken.value) {
                ws.send(JSON.stringify({ type: 'auth', token: authToken.value }));
              }
            }
            return;
          }

          if (msg.type === 'auth') {
            if (msg.payload?.status === 'ok') {
              authenticated.value = true;
              authError.value = '';
              startMtimePolling();
            } else {
              authError.value = t('auth.error.invalid');
              ws.close();
            }
            return;
          }

          window.dispatchEvent(new CustomEvent('ap-ws-message', { detail: msg }));
        };

        ws.onclose = () => {
          wsDisconnected.value = true;
          const jitter = Math.random() * 1000;
          setTimeout(connectWs, reconnectDelay + jitter);
          reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
        };

        ws.onerror = () => { wsDisconnected.value = true; };
      }

      window.addEventListener('ap-send-chat', (e) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'chat_message', text: e.detail.text }));
        }
      });

      function submitAuth() {
        if (!authToken.value.trim()) {
          authError.value = t('auth.error.empty');
          return;
        }
        authError.value = '';
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'auth', token: authToken.value }));
        } else {
          connectWs();
        }
      }

      function refreshAll() {
        globalLoading.value = true;
        for (const fn of _refreshCallbacks) fn();
        showToast(t('toast.refreshed'), 'success', 2000);
        setTimeout(() => { globalLoading.value = false; }, 800);
      }

      // ── Global keyboard shortcuts ──
      function globalKeyDown(e) {
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) return;
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        if (e.key === '?') { e.preventDefault(); showShortcuts.value = !showShortcuts.value; return; }
        if (e.key === 'Escape' && showShortcuts.value) { showShortcuts.value = false; return; }
        if (e.key === '/') {
          e.preventDefault();
          var searchInput = document.querySelector('.main .search-input:not([style*="display: none"])');
          if (searchInput) searchInput.focus();
          return;
        }
        if (e.key === 'r' || e.key === 'R') { e.preventDefault(); refreshAll(); return; }

        const viewMap = { '1': 'dashboard', '2': 'topology', '3': 'capability-map', '4': 'chat', '5': 'operations', '6': 'logs' };
        if (viewMap[e.key]) { e.preventDefault(); view.value = viewMap[e.key]; }
      }

      onMounted(async () => {
        document.addEventListener('keydown', globalKeyDown);
        try {
          const res = await fetch('/api/config');
          const config = await res.json();
          if (config.requires_auth) {
            needsAuth.value = true;
          } else {
            authenticated.value = true;
            startMtimePolling();
          }
        } catch {
          authenticated.value = true;
          startMtimePolling();
        }
        connectWs();
      });

      onUnmounted(() => {
        document.removeEventListener('keydown', globalKeyDown);
        window.removeEventListener('hashchange', syncHashToView);
        window.removeEventListener('popstate', syncHashToView);
        stopMtimePolling();
        if (ws) ws.close();
      });

      return {
        view, sidebarOpen, wsDisconnected, globalLoading,
        needsAuth, authenticated, authToken, authError,
        viewLabel, currentView, submitAuth, refreshAll,
        t, locale, toggleLocale,
        toasts, showShortcuts, shortcutList,
      };
    },
  });

  app.config.errorHandler = (err, instance, info) => {
    console.error('[AgentPlane]', err, info);
  };

  return app;
}
