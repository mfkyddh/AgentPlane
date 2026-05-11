// AgentPlane — Topology view component
// Standalone topology page with own data fetching

const TopologyViewComponent = {
  template: `
    <div>
      <!-- Refresh bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div class="panel-title" style="margin-bottom:0; font-size:16px;">{{ t('topology.title') }}</div>
        <button class="retry-btn" @click="fetchTopology" :disabled="loading"
                style="border-color:var(--accent-green); color:var(--accent-green);">
          {{ loading ? t('action.loading') : t('action.refresh') }}
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading && topology.targets.length === 0">
        <div class="topo-app-grid">
          <div v-for="n in 2" :key="n" class="skeleton-card">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w40"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="error-state">
        <div style="font-size:28px; margin-bottom:8px; opacity:0.5;">&#x26A0;</div>
        <div class="error-state-msg">{{ error }}</div>
        <button class="retry-btn" @click="fetchTopology">{{ t('action.retry') }}</button>
      </div>

      <!-- Empty -->
      <div v-else-if="topology.targets.length === 0" class="empty-state">
        <div class="empty-state-icon">&#x1F310;</div>
        <div class="empty-state-title">{{ t('topology.no_targets') }}</div>
        <div class="empty-state-hint" v-html="t('topology.no_targets_hint')"></div>
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
            <span class="topo-badge">{{ target.apps.length }} {{ t('topology.apps') }}</span>
          </div>

          <!-- Target details -->
          <div v-if="expandedTargets.has(target.target)" class="topo-children">
            <!-- Apps -->
            <div v-if="target.apps.length > 0" class="topo-section">
              <div class="topo-section-label">{{ t('dashboard.applications') }}</div>
              <div class="topo-app-grid">
                <div v-for="app in target.apps" :key="app.app"
                     class="topo-app-card" @click="selectApp(target.target, app)">
                  <div class="topo-app-name">
                    <span class="status-dot" :class="appStatusClass(app.status)"></span>
                    {{ app.app }}
                  </div>
                  <div v-if="app.image" class="topo-app-image">{{ app.image }}</div>
                  <div class="topo-app-detail">
                    <span v-if="app.port">:{{ app.port }}</span>
                    <span v-if="app.control_plane">{{ app.control_plane }}</span>
                  </div>
                  <a v-if="app.public_url" :href="app.public_url" target="_blank" class="topo-app-url"
                     @click.stop>{{ app.public_url }}</a>
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
              <div class="topo-section-label">{{ t('dashboard.services') }}</div>
              <div class="topo-app-grid">
                <div v-for="svc in target.services" :key="svc.name" class="topo-svc-card">
                  <span class="status-dot" :class="serviceStatusClass(svc.status)"></span>
                  <span class="topo-svc-name">{{ svc.name }}</span>
                  <span class="topo-svc-kind">{{ svc.kind }}</span>
                </div>
              </div>
            </div>

            <div v-if="target.apps.length === 0 && target.services.length === 0"
                 class="empty-state" style="padding:16px;">
              <div class="empty-state-hint">{{ t('topology.no_items') }}</div>
            </div>
          </div>
        </div>

        <!-- Generated timestamp -->
        <div v-if="topology.generated_at" class="generated-ts">
          {{ t('dashboard.generated') }} {{ formatTime(topology.generated_at) }}
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="detailPanel.visible" class="detail-overlay" @click.self="closeDetail">
        <div class="detail-panel">
          <div class="detail-header">
            <span class="detail-title">{{ detailPanel.title }}</span>
            <button class="detail-close" @click="closeDetail">&times;</button>
          </div>
          <div class="detail-body">
            <div v-if="detailPanel.loading" class="skeleton-card">
              <div class="skeleton skeleton-line w80"></div>
              <div class="skeleton skeleton-line w60"></div>
              <div class="skeleton skeleton-line w40"></div>
            </div>
            <div v-else-if="detailPanel.error" style="color:var(--accent-red);">{{ detailPanel.error }}</div>
            <div v-else>
              <div v-for="(val, key) in detailPanel.data" :key="key" class="detail-field">
                <div class="detail-key">{{ key }}</div>
                <div class="detail-val">{{ formatDetailVal(val) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,

  setup() {
    const authToken = Vue.inject('authToken', Vue.ref(''));
    const { t } = useI18n();
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
        if (res.status === 401) { error.value = t('error.auth_required'); return; }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        topology.value = await res.json();
        if (topology.value.targets.length > 0 && expandedTargets.value.size === 0) {
          expandedTargets.value.add(topology.value.targets[0].target);
        }
      } catch (e) {
        error.value = t('error.load_topology') + ': ' + e.message;
      } finally {
        loading.value = false;
      }
    }

    // Shared polling
    useDataPoller(fetchTopology);

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

    function closeDetail() { detailPanel.value.visible = false; }

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

    return {
      topology, loading, error, expandedTargets, detailPanel,
      fetchTopology, toggleTarget, selectApp, closeDetail,
      appStatusClass, serviceStatusClass, formatTime, formatDetailVal,
      t,
    };
  },
};
