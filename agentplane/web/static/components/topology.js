// AgentPlane — Topology view component
// Standalone topology page with own data fetching, expand/collapse all, search

const TopologyViewComponent = {
  template: `
    <div>
      <!-- Header bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
        <div class="panel-title" style="margin-bottom:0; font-size:16px;">{{ t('topology.title') }}</div>
        <div style="display:flex; gap:8px; align-items:center;">
          <span v-if="topology.targets.length > 0" class="panel-count" style="margin-right:4px;">{{ connectedCount }}/{{ topology.targets.length }} {{ t('topology.connected') }}</span>
          <input v-model="searchQuery" class="search-input" :placeholder="t('topology.search')" :aria-label="t('topology.search')">
          <button class="btn-ghost" @click="toggleAll" :disabled="topology.targets.length === 0" :aria-expanded="allExpanded">
            {{ allExpanded ? t('action.collapse_all') : t('action.expand_all') }}
          </button>
          <button class="retry-btn" @click="fetchTopology" :disabled="loading"
                  style="border-color:var(--accent-green); color:var(--accent-green);">
            {{ loading ? t('action.loading') : t('action.refresh') }}
          </button>
        </div>
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
      <div v-else-if="filteredTargets.length === 0" class="empty-state">
        <div class="empty-state-icon">&#x1F310;</div>
        <div class="empty-state-title">{{ searchQuery ? t('topology.no_match') : t('topology.no_targets') }}</div>
        <div class="empty-state-hint" v-if="!searchQuery" v-html="t('topology.no_targets_hint')"></div>
      </div>

      <!-- Topology tree -->
      <div v-else>
        <div v-for="target in filteredTargets" :key="target.target" class="topo-target">
          <div class="topo-target-header" @click="toggleTarget(target.target)" :aria-expanded="expandedTargets.has(target.target)" role="button" tabindex="0" @keydown.enter="toggleTarget(target.target)" @keydown.space.prevent="toggleTarget(target.target)">
            <span class="topo-expand">{{ expandedTargets.has(target.target) ? '&#x25BC;' : '&#x25B6;' }}</span>
            <span class="status-dot" :class="target.status"></span>
            <span class="topo-target-name">{{ target.target }}</span>
            <span class="topo-target-meta">{{ target.hostname }} &middot; {{ target.ip || 'local' }}</span>
            <span class="topo-badge">{{ target.apps.length }} {{ t('topology.apps') }}</span>
          </div>

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
                  <div v-if="app.dependencies && app.dependencies.length > 0" class="topo-deps">
                    <span v-for="dep in app.dependencies" :key="dep.kind" class="topo-dep-tag">{{ dep.kind }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Services -->
            <div v-if="target.services && target.services.length > 0" class="topo-section">
              <div class="topo-section-label">{{ t('dashboard.services') }}</div>
              <div class="topo-app-grid">
                <div v-for="svc in target.services" :key="svc.name" class="topo-svc-card">
                  <span class="status-dot" :class="serviceStatusClass(svc.status)"></span>
                  <span class="topo-svc-name">{{ svc.name }}</span>
                  <span class="topo-svc-kind">{{ svc.kind }}</span>
                </div>
              </div>
            </div>

            <div v-if="(!target.apps || target.apps.length === 0) && (!target.services || target.services.length === 0)"
                 class="empty-state" style="padding:16px;">
              <div class="empty-state-hint">{{ t('topology.no_items') }}</div>
            </div>
          </div>
        </div>

        <div v-if="topology.generated_at" class="generated-ts">
          {{ t('dashboard.generated') }} {{ formatTimestamp(topology.generated_at) }}
        </div>
      </div>

      <!-- Detail panel -->
      <div v-if="detailPanel.visible" class="detail-overlay" @click.self="closeDetail" @keydown.esc="closeDetail">
        <div class="detail-panel">
          <div class="detail-header">
            <span class="detail-title">{{ detailPanel.title }}</span>
            <button class="detail-close" @click="closeDetail" aria-label="Close detail panel">&times;</button>
          </div>
          <div class="detail-body">
            <div v-if="detailPanel.loading" class="skeleton-card">
              <div class="skeleton skeleton-line w80"></div>
              <div class="skeleton skeleton-line w60"></div>
              <div class="skeleton skeleton-line w40"></div>
            </div>
            <div v-else-if="detailPanel.error" style="color:var(--accent-red);">{{ detailPanel.error }}</div>
            <div v-else>
              <template v-for="(val, key) in detailPanel.data" :key="key">
                <div v-if="!isDetailHidden(key)" class="detail-field">
                  <div class="detail-key">
                    {{ key }}
                    <button class="detail-copy-btn" @click="copyDetailVal(val)" :title="t('action.copy')">&#x2398;</button>
                  </div>
                  <div v-if="isDetailUrl(key, val)" class="detail-val">
                    <a :href="val" target="_blank" class="cell-link">{{ truncateUrl(val) }}</a>
                  </div>
                  <div v-else-if="isDetailStatus(key)" class="detail-val">
                    <span class="status-badge" :class="resultBadgeClass(val)">{{ val || '-' }}</span>
                  </div>
                  <div v-else class="detail-val">{{ formatDetailVal(val) }}</div>
                </div>
              </template>
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
    const searchQuery = Vue.ref('');
    const debouncedSearch = useDebounce(searchQuery, 200);
    const filteredTargets = Vue.ref([]);

    const { detailPanel, openDetail, closeDetail } = useDetailPanel(authToken);

    const allExpanded = computed(() =>
      topology.value.targets.length > 0 && topology.value.targets.every(t => expandedTargets.value.has(t.target))
    );

    const connectedCount = computed(() =>
      topology.value.targets.filter(t => t.status === 'connected').length
    );

    // Watch debounced search to trigger filtering
    Vue.watch(debouncedSearch, filterTargets);

    function filterTargets() {
      const q = searchQuery.value.toLowerCase().trim();
      if (!q) {
        filteredTargets.value = topology.value.targets;
      } else {
        filteredTargets.value = topology.value.targets.filter(t =>
          t.target.toLowerCase().includes(q) ||
          (t.hostname && t.hostname.toLowerCase().includes(q)) ||
          (t.ip && t.ip.includes(q)) ||
          (t.apps && t.apps.some(a => a.app.toLowerCase().includes(q)))
        );
      }
    }

    async function fetchTopology() {
      loading.value = true;
      error.value = '';
      try {
        const res = await apiFetch('/api/topology', authToken);
        if (res.status === 401) { error.value = t('error.auth_required'); return; }
        if (!res.ok) throw new Error('HTTP ' + res.status);
        topology.value = await res.json();
        if (topology.value.targets.length > 0 && expandedTargets.value.size === 0) {
          expandedTargets.value.add(topology.value.targets[0].target);
        }
        filterTargets();
      } catch (e) {
        error.value = t('error.load_topology') + ': ' + e.message;
      } finally {
        loading.value = false;
      }
    }

    useDataPoller(fetchTopology);

    function toggleTarget(target) {
      if (expandedTargets.value.has(target)) {
        expandedTargets.value.delete(target);
      } else {
        expandedTargets.value.add(target);
      }
    }

    function toggleAll() {
      if (allExpanded.value) {
        expandedTargets.value = new Set();
      } else {
        expandedTargets.value = new Set(topology.value.targets.map(t => t.target));
      }
    }

    function selectApp(target, app) {
      openDetail(`${app.app} (${target})`, `/api/apps/${target}/${app.app}`);
    }

    function copyDetailVal(val) {
      copyToClipboard(formatDetailVal(val)).then(ok => {
        if (ok) showToast(t('toast.copied'), 'success', 1500);
      });
    }

    return {
      topology, loading, error, expandedTargets, detailPanel,
      searchQuery, filteredTargets, allExpanded, connectedCount,
      fetchTopology, toggleTarget, toggleAll, selectApp, closeDetail, copyDetailVal,
      filterTargets,
      appStatusClass, serviceStatusClass, resultBadgeClass, formatTimestamp, formatDetailVal, truncateUrl,
      isDetailUrl, isDetailStatus, isDetailHidden,
      t,
    };
  },
};
