// AgentPlane — Vue app setup, state management, routing, shared polling
// Loaded AFTER components/*.js, i18n/index.js, and Vue CDN

const { createApp, ref, computed, provide, inject, onMounted, nextTick, onUnmounted } = Vue;

// ── Shared polling ──
const _refreshCallbacks = new Set();

function useDataPoller(refreshFn) {
  onMounted(() => {
    _refreshCallbacks.add(refreshFn);
    refreshFn();  // Fetch immediately on mount so late-mounting components load data
  });
  onUnmounted(() => _refreshCallbacks.delete(refreshFn));
}

// ── App factory ──
function createAgentPlaneApp() {
  const app = createApp({
    setup() {
      const view = ref('dashboard');
      const sidebarOpen = ref(false);
      const loading = ref(true);
      const loadError = ref('');
      const wsDisconnected = ref(false);
      const needsAuth = ref(false);
      const authenticated = ref(false);
      const authToken = ref('');
      const authError = ref('');

      // i18n
      const { locale, t, toggleLocale } = useI18n();

      const viewLabel = computed(() => {
        const labels = { dashboard: t('topbar.overview'), topology: t('topbar.topology'), 'capability-map': t('topbar.capabilities'), chat: t('topbar.chat'), operations: t('topbar.operations') || 'Operations', logs: t('topbar.logs') || 'Live Logs' };
        return labels[view.value] || t('topbar.overview');
      });

      const currentView = computed(() => {
        const map = { dashboard: 'dashboard-view', topology: 'topology-view', 'capability-map': 'capability-map-view', chat: 'chat-view', operations: 'operations-view', logs: 'logs-view' };
        return map[view.value] || 'dashboard-view';
      });

      provide('authToken', authToken);

      let ws = null;
      let mtimePoller = null;
      let lastMtime = 0;
      let reconnectDelay = 1000;
      const MAX_RECONNECT_DELAY = 30000;

      function apiFetch(url) {
        const headers = {};
        if (authenticated.value && authToken.value) {
          headers['Authorization'] = `Bearer ${authToken.value}`;
        }
        return fetch(url, { headers });
      }

      function startMtimePolling() {
        // Seed lastMtime to avoid redundant refresh on first poll cycle
        apiFetch('/api/mtime').then(res => res.json()).then(data => {
          lastMtime = data.mtime || 0;
        }).catch(() => {});

        mtimePoller = setInterval(async () => {
          try {
            const res = await apiFetch('/api/mtime');
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
          const msg = JSON.parse(event.data);

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

          // Forward chat messages to chat component via event
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

      // Listen for chat send events from ChatComponent
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
        for (const fn of _refreshCallbacks) fn();
      }

      onMounted(async () => {
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
        stopMtimePolling();
        if (ws) ws.close();
      });

      return {
        view, sidebarOpen, loading, loadError, wsDisconnected,
        needsAuth, authenticated, authToken, authError,
        viewLabel, currentView, submitAuth, refreshAll,
        t, locale, toggleLocale,
      };
    },
  });

  return app;
}
