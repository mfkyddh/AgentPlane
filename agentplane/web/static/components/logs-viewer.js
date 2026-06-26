// AgentPlane — Real-time Logs Viewer component
// Streams Docker container logs via WebSocket
// Dynamic targets from hosts API

const LogsViewerComponent = {
  template: `
    <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; padding:20px;">
      <!-- Header -->
      <div class="panel" style="margin-bottom:20px;">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0110.25 10H7.061l-2.574 2.573A.25.25 0 014 12.354V10H1.75A1.75 1.75 0 010 8.25v-5.5C0 1.784.784 1 1.75 1z"/></svg>
            {{ t('logs.title') }}
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            <span v-if="connected" class="status-badge success">
              <span class="status-dot online"></span>
              {{ t('logs.connected') }}
            </span>
            <span v-else-if="connecting" class="status-badge warning">
              {{ t('logs.connecting') }}
            </span>
            <span v-else class="status-badge error">
              <span class="status-dot offline"></span>
              {{ t('logs.disconnected') }}
            </span>
          </div>
        </div>
      </div>

      <!-- Connection Form -->
      <div class="panel" style="margin-bottom:16px;">
        <div class="panel-body">
          <div class="log-connection-form">
            <select v-model="selectedTarget" class="form-select">
              <option value="">{{ t('logs.select_target') }}</option>
              <option v-for="tgt in targets" :key="tgt" :value="tgt">{{ tgt }}</option>
            </select>
            <input v-model="containerName" class="form-input"
                   :placeholder="t('logs.container_name')"
                   @keyup.enter="connect">
            <button v-if="!connected" class="btn btn-primary" @click="connect"
                    :disabled="!selectedTarget || !containerName || connecting">
              {{ t('logs.connect') }}
            </button>
            <button v-else class="btn btn-danger" @click="disconnect">
              {{ t('logs.disconnect') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Log Output -->
      <div class="panel" style="flex:1; display:flex; flex-direction:column;">
        <div class="panel-header">
          <div class="panel-title">{{ t('logs.output') }}</div>
          <div style="display:flex; gap:8px; align-items:center;">
            <span class="panel-count" v-if="logs.length > 0">{{ logs.length }} {{ t('logs.lines') }}</span>
            <button class="btn-ghost btn-sm" @click="copyLogs" :disabled="logs.length === 0">
              {{ t('action.copy') }}
            </button>
            <button class="btn-ghost btn-sm" @click="clearLogs">
              {{ t('logs.clear') }}
            </button>
            <label class="toggle-label">
              <input type="checkbox" v-model="autoScroll" class="toggle-input">
              {{ t('logs.auto_scroll') }}
            </label>
          </div>
        </div>
        <div class="log-output" ref="logContainer">
          <div v-if="logs.length === 0" class="log-empty">
            {{ connected ? t('logs.waiting') : t('logs.not_connected') }}
          </div>
          <div v-for="(log, idx) in logs" :key="idx" class="log-line" :class="log.type">
            <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
            <span class="log-text">{{ log.line }}</span>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const { t } = useI18n();
    const authToken = Vue.inject('authToken', Vue.ref(''));

    const targets = ref([]);
    const selectedTarget = ref('');
    const containerName = ref('');
    const connected = ref(false);
    const connecting = ref(false);
    const logs = ref([]);
    const autoScroll = ref(true);
    const logContainer = ref(null);

    let ws = null;

    // Fetch dynamic targets
    async function fetchTargets() {
      try {
        const res = await apiFetch('/api/hosts', authToken);
        const data = await res.json();
        targets.value = (data.hosts || []).map(h => h.target).filter(Boolean);
      } catch { /* keep empty */ }
    }

    Vue.onMounted(fetchTargets);

    function connect() {
      if (!selectedTarget.value || !containerName.value) return;

      connecting.value = true;
      logs.value = [];

      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${location.host}/ws/logs/${selectedTarget.value}/${containerName.value}`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        connected.value = true;
        connecting.value = false;
        addLog('system', t('logs.connected_to') + ' ' + containerName.value + ' @ ' + selectedTarget.value);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'log') {
            addLog('output', msg.payload.line);
          } else if (msg.type === 'error') {
            addLog('error', msg.payload.message);
          }
        } catch {
          addLog('output', event.data);
        }
      };

      ws.onerror = () => {
        addLog('error', t('logs.ws_error'));
      };

      ws.onclose = () => {
        connected.value = false;
        connecting.value = false;
        addLog('system', t('logs.disconnected'));
      };
    }

    function disconnect() {
      if (ws) {
        ws.close();
        ws = null;
      }
    }

    function addLog(type, line) {
      logs.value.push({ type, line, timestamp: new Date().toISOString() });
      if (logs.value.length > 1000) {
        logs.value = logs.value.slice(-1000);
      }
      if (autoScroll.value && logContainer.value) {
        nextTick(() => {
          logContainer.value.scrollTop = logContainer.value.scrollHeight;
        });
      }
    }

    function clearLogs() {
      logs.value = [];
    }

    function copyLogs() {
      const text = logs.value.map(l => `[${formatLogTime(l.timestamp)}] ${l.line}`).join('\n');
      copyToClipboard(text).then(ok => {
        if (ok) showToast(t('toast.copied'), 'success', 1500);
      });
    }

    onUnmounted(() => {
      disconnect();
    });

    return {
      targets, selectedTarget, containerName, connected, connecting,
      logs, autoScroll, logContainer, connect, disconnect, clearLogs, copyLogs,
      formatLogTime, t
    };
  }
};
