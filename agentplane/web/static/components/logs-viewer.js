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
          <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <input v-model="logSearch" class="search-input" :placeholder="t('logs.search')" style="width:160px;min-width:120px;" :aria-label="t('logs.search')">
            <select v-model="logLevelFilter" class="select-sm" :aria-label="t('logs.all_levels')">
              <option value="">{{ t('logs.all_levels') }}</option>
              <option value="error">ERROR</option>
              <option value="system">SYSTEM</option>
              <option value="output">OUTPUT</option>
            </select>
            <span class="panel-count" v-if="filteredLogs.length > 0" :style="logs.length > 800 ? 'color:var(--accent-yellow);' : ''">{{ filteredLogs.length }}/{{ logs.length }}{{ logs.length >= 1000 ? '/1000' : '' }} {{ t('logs.lines') }}</span>
            <button v-if="connected" class="btn-ghost btn-sm" @click="togglePause">
              {{ paused ? t('logs.resume') : t('logs.pause') }}
            </button>
            <button class="btn-ghost btn-sm" @click="copyLogs" :disabled="logs.length === 0">
              {{ t('action.copy') }}
            </button>
            <button class="btn-ghost btn-sm" @click="downloadLogs" :disabled="logs.length === 0">
              &#x2B07; {{ t('logs.download') }}
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
        <div v-if="paused" class="log-paused-banner">
          &#x23F8; {{ t('logs.paused_hint') }}
        </div>
        <div class="log-output" :class="{ paused: paused }" ref="logContainer" role="log" aria-live="off">
          <div v-if="filteredLogs.length === 0" class="log-empty">
            {{ connected ? (logSearch ? t('logs.no_match') : t('logs.waiting')) : t('logs.not_connected') }}
          </div>
          <div v-for="(log, idx) in filteredLogs" :key="log._id" class="log-line" :class="log.type">
            <span class="log-line-num">{{ idx + 1 }}</span>
            <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
            <span class="log-text" v-html="highlightSearch(log.line)"></span>
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
    const logSearch = ref('');
    const debouncedSearch = useDebounce(logSearch, 150);
    const logLevelFilter = ref('');
    const paused = ref(false);
    let _logId = 0;

    let ws = null;
    let _reconnectTimer = null;
    let _reconnectAttempts = 0;
    const MAX_RECONNECT = 3;
    let _userDisconnected = false;

    // Filtered logs computed
    const filteredLogs = computed(() => {
      let result = logs.value;
      if (logLevelFilter.value) {
        result = result.filter(l => l.type === logLevelFilter.value);
      }
      const q = debouncedSearch.value.toLowerCase().trim();
      if (q) {
        result = result.filter(l => l.line.toLowerCase().includes(q));
      }
      return result;
    });

    function highlightSearch(line) {
      const q = debouncedSearch.value.trim();
      if (!q) return escapeHtml(line);
      const escaped = escapeHtml(line);
      const regex = new RegExp('(' + escapeRegex(escapeHtml(q)) + ')', 'gi');
      return escaped.replace(regex, '<mark>$1</mark>');
    }

    function togglePause() {
      paused.value = !paused.value;
    }

    // Fetch dynamic targets
    async function fetchTargets() {
      targets.value = await fetchTargetList(authToken);
    }

    Vue.onMounted(fetchTargets);

    function connect() {
      if (!selectedTarget.value || !containerName.value) return;

      connecting.value = true;
      logs.value = [];
      _logId = 0;
      paused.value = false;
      _reconnectAttempts = 0;
      _userDisconnected = false;
      if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }

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

        // Auto-reconnect if not user-initiated
        if (!_userDisconnected && _reconnectAttempts < MAX_RECONNECT) {
          _reconnectAttempts++;
          var delay = _reconnectAttempts * 2000;
          addLog('system', t('logs.reconnect_attempt') + ' ' + _reconnectAttempts + '/' + MAX_RECONNECT);
          _reconnectTimer = setTimeout(function () { connect(); }, delay);
        }
      };
    }

    function disconnect() {
      _userDisconnected = true;
      if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
      if (ws) {
        ws.close();
        ws = null;
      }
    }

    function addLog(type, line) {
      if (paused.value) return;
      logs.value.push({ type, line, timestamp: new Date().toISOString(), _id: ++_logId });
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
      _logId = 0;
    }

    function copyLogs() {
      const items = filteredLogs.value.length > 0 ? filteredLogs.value : logs.value;
      const text = items.map(l => `[${formatLogTime(l.timestamp)}] [${l.type.toUpperCase()}] ${l.line}`).join('\n');
      copyToClipboard(text).then(ok => {
        if (ok) showToast(t('toast.copied'), 'success', 1500);
      });
    }

    function downloadLogs() {
      var items = filteredLogs.value.length > 0 ? filteredLogs.value : logs.value;
      if (items.length === 0) return;
      var text = items.map(function (l) {
        return '[' + formatLogTime(l.timestamp) + '] [' + l.type.toUpperCase() + '] ' + l.line;
      }).join('\n');
      var blob = new Blob([text], { type: 'text/plain' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'logs-' + (selectedTarget.value || 'unknown') + '-' + new Date().toISOString().slice(0, 19).replace(/:/g, '-') + '.txt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(t('logs.download_success') || 'Logs downloaded', 'success', 2000);
    }

    onUnmounted(() => {
      _userDisconnected = true;
      if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
      disconnect();
    });

    return {
      targets, selectedTarget, containerName, connected, connecting,
      logs, filteredLogs, autoScroll, logContainer, connect, disconnect,
      clearLogs, copyLogs, downloadLogs, formatLogTime, t,
      logSearch, logLevelFilter, paused, togglePause, highlightSearch,
    };
  }
};
