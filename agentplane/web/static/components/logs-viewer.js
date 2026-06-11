// AgentPlane — Real-time Logs Viewer component
// Streams Docker container logs via WebSocket

const LogsViewerComponent = {
  template: `
    <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; padding:20px;">
      <!-- Header -->
      <div class="panel" style="margin-bottom:20px;">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0110.25 10H7.061l-2.574 2.573A.25.25 0 014 12.354V10H1.75A1.75 1.75 0 010 8.25v-5.5C0 1.784.784 1 1.75 1z"/></svg>
            {{ t('logs.title') || 'Live Logs' }}
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            <span v-if="connected" class="status-badge success">
              <span class="status-dot online"></span>
              {{ t('logs.connected') || 'Connected' }}
            </span>
            <span v-else-if="connecting" class="status-badge warning">
              {{ t('logs.connecting') || 'Connecting...' }}
            </span>
            <span v-else class="status-badge error">
              <span class="status-dot offline"></span>
              {{ t('logs.disconnected') || 'Disconnected' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Connection Form -->
      <div class="panel" style="margin-bottom:16px;">
        <div class="panel-body">
          <div class="log-connection-form">
            <select v-model="selectedTarget" class="form-select">
              <option value="">{{ t('logs.select_target') || 'Select Target' }}</option>
              <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
            </select>
            <input v-model="containerName" class="form-input" 
                   :placeholder="t('logs.container_name') || 'Container Name (e.g. postgres18-prod)'"
                   @keyup.enter="connect">
            <button v-if="!connected" class="btn btn-primary" @click="connect" 
                    :disabled="!selectedTarget || !containerName || connecting">
              {{ t('logs.connect') || 'Connect' }}
            </button>
            <button v-else class="btn btn-danger" @click="disconnect">
              {{ t('logs.disconnect') || 'Disconnect' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Log Output -->
      <div class="panel" style="flex:1; display:flex; flex-direction:column;">
        <div class="panel-header">
          <div class="panel-title">{{ t('logs.output') || 'Log Output' }}</div>
          <div style="display:flex; gap:8px;">
            <button class="btn-ghost btn-sm" @click="clearLogs">
              {{ t('logs.clear') || 'Clear' }}
            </button>
            <label class="toggle-label">
              <input type="checkbox" v-model="autoScroll" class="toggle-input">
              {{ t('logs.auto_scroll') || 'Auto Scroll' }}
            </label>
          </div>
        </div>
        <div class="log-output" ref="logContainer">
          <div v-if="logs.length === 0" class="log-empty">
            {{ connected ? t('logs.waiting') || 'Waiting for logs...' : t('logs.not_connected') || 'Not connected. Select a target and container to start.' }}
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
    const authToken = inject('authToken');
    
    const targets = ref(['prod0-main', 'wsl']);
    const selectedTarget = ref('');
    const containerName = ref('');
    const connected = ref(false);
    const connecting = ref(false);
    const logs = ref([]);
    const autoScroll = ref(true);
    const logContainer = ref(null);
    
    let ws = null;

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
        addLog('system', 'Connected to ' + containerName.value + ' on ' + selectedTarget.value);
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
      
      ws.onerror = (error) => {
        addLog('error', 'WebSocket error');
        console.error('WebSocket error:', error);
      };
      
      ws.onclose = () => {
        connected.value = false;
        connecting.value = false;
        addLog('system', 'Disconnected');
      };
    }
    
    function disconnect() {
      if (ws) {
        ws.close();
        ws = null;
      }
    }
    
    function addLog(type, line) {
      logs.value.push({
        type,
        line,
        timestamp: new Date().toISOString()
      });
      
      // Keep last 1000 lines
      if (logs.value.length > 1000) {
        logs.value = logs.value.slice(-1000);
      }
      
      // Auto scroll
      if (autoScroll.value && logContainer.value) {
        nextTick(() => {
          logContainer.value.scrollTop = logContainer.value.scrollHeight;
        });
      }
    }
    
    function clearLogs() {
      logs.value = [];
    }
    
    function formatLogTime(ts) {
      if (!ts) return '';
      try {
        const d = new Date(ts);
        return d.toLocaleTimeString();
      } catch {
        return '';
      }
    }
    
    onUnmounted(() => {
      disconnect();
    });

    return {
      targets, selectedTarget, containerName, connected, connecting,
      logs, autoScroll, logContainer, connect, disconnect, clearLogs,
      formatLogTime, t
    };
  }
};
