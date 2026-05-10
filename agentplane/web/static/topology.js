// Topology Vue component for AgentPlane WebUI
// Loaded as a separate file to prevent index.html bloat

const TopologyComponent = {
  template: `
    <div>
      <!-- Refresh bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div class="section-title" style="margin-bottom:0;">Resource Topology</div>
        <button class="retry-btn" @click="fetchTopology" :disabled="loading"
                style="border-color:#00d4aa40; color:#00d4aa;">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading && topology.targets.length === 0">
        <div class="cards-grid">
          <div v-for="n in 2" :key="n" class="skeleton-card">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w40"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="error-state">
        <div class="error-state-icon">&#x26A0;</div>
        <div class="error-state-msg">{{ error }}</div>
        <button class="retry-btn" @click="fetchTopology">Retry</button>
      </div>

      <!-- Empty -->
      <div v-else-if="topology.targets.length === 0" class="empty-state">
        <div class="empty-state-icon">&#x1F310;</div>
        <div class="empty-state-title">No targets found</div>
        <div class="empty-state-hint">
          Run <code>agentplane infra inventory &lt;target&gt;</code> to register a server
        </div>
      </div>

      <!-- Topology tree -->
      <div v-else>
        <div v-for="target in topology.targets" :key="target.target" class="topo-target">
          <!-- Target header -->
          <div class="topo-target-header" @click="toggleTarget(target.target)">
            <span class="topo-expand">{{ expandedTargets.has(target.target) ? '&#x25BC;' : '&#x25B6;' }}</span>
            <span class="status-dot" :class="target.status"></span>
            <span class="topo-target-name">{{ target.target }}</span>
            <span class="topo-target-meta">{{ target.hostname }} &middot; {{ target.ip || 'local' }}</span>
            <span class="topo-badge">{{ target.apps.length }} apps</span>
          </div>

          <!-- Target details -->
          <div v-if="expandedTargets.has(target.target)" class="topo-children">
            <!-- Apps -->
            <div v-if="target.apps.length > 0" class="topo-section">
              <div class="topo-section-label">Applications</div>
              <div class="cards-grid">
                <div v-for="app in target.apps" :key="app.app"
                     class="server-card topo-app-card" @click="selectApp(target.target, app)">
                  <div>
                    <span class="status-dot" :class="appStatusClass(app.status)"></span>
                    <span class="server-hostname">{{ app.app }}</span>
                  </div>
                  <div v-if="app.image" class="server-ip">{{ app.image }}</div>
                  <div class="server-meta">
                    <span v-if="app.port">Port: {{ app.port }}</span>
                    <span v-if="app.control_plane"> &middot; {{ app.control_plane }}</span>
                  </div>
                  <div v-if="app.public_url" class="server-meta">
                    <a :href="app.public_url" target="_blank" class="app-url">{{ app.public_url }}</a>
                  </div>
                  <div v-if="app.dependencies.length > 0" class="topo-deps">
                    <span v-for="dep in app.dependencies" :key="dep.kind" class="topo-dep-tag">
                      {{ dep.kind }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Services -->
            <div v-if="target.services.length > 0" class="topo-section">
              <div class="topo-section-label">Services</div>
              <div class="cards-grid">
                <div v-for="svc in target.services" :key="svc.name" class="server-card">
                  <div>
                    <span class="status-dot" :class="serviceStatusClass(svc.status)"></span>
                    <span class="server-hostname">{{ svc.name }}</span>
                  </div>
                  <div class="server-meta">{{ svc.kind }}</div>
                </div>
              </div>
            </div>

            <div v-if="target.apps.length === 0 && target.services.length === 0"
                 class="empty-state" style="padding:24px;">
              <div class="empty-state-hint">No apps or services on this target</div>
            </div>
          </div>
        </div>

        <!-- Generated timestamp -->
        <div v-if="topology.generated_at" style="text-align:right; margin-top:16px; font-size:12px; color:#666;">
          Generated {{ formatTime(topology.generated_at) }}
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="detailPanel.visible" class="topo-detail-overlay" @click.self="closeDetail">
        <div class="topo-detail-panel">
          <div class="topo-detail-header">
            <span class="topo-detail-title">{{ detailPanel.title }}</span>
            <button class="topo-detail-close" @click="closeDetail">&times;</button>
          </div>
          <div class="topo-detail-body">
            <div v-if="detailPanel.loading" class="skeleton-card">
              <div class="skeleton skeleton-line w80"></div>
              <div class="skeleton skeleton-line w60"></div>
              <div class="skeleton skeleton-line w40"></div>
            </div>
            <div v-else-if="detailPanel.error" style="color:#ff6b6b;">{{ detailPanel.error }}</div>
            <div v-else>
              <div v-for="(val, key) in detailPanel.data" :key="key" class="topo-detail-field">
                <div class="topo-detail-key">{{ key }}</div>
                <div class="topo-detail-val">{{ formatDetailVal(val) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,

  setup() {
    const authToken = Vue.inject('authToken', Vue.ref(''));
    const topology = Vue.ref({ targets: [], generated_at: '' });
    const loading = Vue.ref(false);
    const error = Vue.ref('');
    const expandedTargets = Vue.ref(new Set());
    const detailPanel = Vue.ref({ visible: false, title: '', data: null, loading: false, error: '' });

    function getAuthHeaders() {
      const headers = {};
      if (authToken.value) headers['Authorization'] = `Bearer ${authToken.value}`;
      return headers;
    }

    async function fetchTopology() {
      loading.value = true;
      error.value = '';
      try {
        const res = await fetch('/api/topology', { headers: getAuthHeaders() });
        if (res.status === 401) { error.value = 'Authentication required'; return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        topology.value = await res.json();
        // Auto-expand first target
        if (topology.value.targets.length > 0 && expandedTargets.value.size === 0) {
          expandedTargets.value.add(topology.value.targets[0].target);
        }
      } catch (e) {
        error.value = `Failed to load topology: ${e.message}`;
      } finally {
        loading.value = false;
      }
    }

    function toggleTarget(target) {
      if (expandedTargets.value.has(target)) {
        expandedTargets.value.delete(target);
      } else {
        expandedTargets.value.add(target);
      }
    }

    async function selectApp(target, app) {
      detailPanel.value = { visible: true, title: `${app.app} (${target})`, data: null, loading: true, error: '' };
      try {
        const res = await fetch(`/api/apps/${target}/${app.app}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        detailPanel.value.data = await res.json();
      } catch (e) {
        detailPanel.value.error = e.message;
      } finally {
        detailPanel.value.loading = false;
      }
    }

    function closeDetail() {
      detailPanel.value.visible = false;
    }

    function appStatusClass(status) {
      if (!status || status === 'unknown') return 'unknown';
      return 'connected';
    }

    function serviceStatusClass(status) {
      if (!status) return 'unknown';
      const s = String(status).toLowerCase();
      if (s.includes('running') || s.includes('active')) return 'connected';
      if (s.includes('error') || s.includes('fail')) return 'error';
      return 'unknown';
    }

    function formatTime(ts) {
      if (!ts) return '';
      try { return new Date(ts).toLocaleString(); } catch { return ts; }
    }

    function formatDetailVal(val) {
      if (val === null || val === undefined) return '-';
      if (typeof val === 'object') return JSON.stringify(val, null, 2);
      return String(val);
    }

    Vue.onMounted(fetchTopology);

    return {
      topology, loading, error, expandedTargets, detailPanel,
      fetchTopology, toggleTarget, selectApp, closeDetail,
      appStatusClass, serviceStatusClass, formatTime, formatDetailVal,
    };
  },
};
