// AgentPlane — Dashboard component
// KPI stats, resource topology (inline), applications table, hosts, operations

const DashboardComponent = {
  template: `
    <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column;">
      <!-- Loading skeleton -->
      <template v-if="loading">
        <div class="stats-row">
          <div v-for="n in 4" :key="n" class="skeleton-card">
            <div class="skeleton skeleton-line w40"></div>
            <div class="skeleton skeleton-line w60" style="height:24px;margin-top:8px;"></div>
          </div>
        </div>
        <div class="content-grid">
          <div class="skeleton-card"><div class="skeleton skeleton-line w80"></div><div class="skeleton skeleton-line w60"></div></div>
          <div class="skeleton-card"><div class="skeleton skeleton-line w80"></div><div class="skeleton skeleton-line w60"></div></div>
        </div>
      </template>

      <!-- Error state -->
      <div v-else-if="loadError" class="error-state" style="flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center;">
        <div style="font-size:32px; margin-bottom:12px; opacity:0.5;">&#x26A0;</div>
        <div class="error-state-msg">{{ loadError }}</div>
        <button class="retry-btn" @click="fetchDashboard">{{ t('action.retry') }}</button>
      </div>

      <!-- Dashboard content -->
      <template v-else>
        <!-- KPI Stats -->
        <div class="stats-row">
          <div class="stat-card" @click="navigateToView('topology')" style="cursor:pointer;">
            <div class="stat-label">{{ t('dashboard.hosts') }}</div>
            <div class="stat-value blue">{{ hosts.length }}</div>
            <div class="stat-detail">
              <span v-if="connectedHosts > 0">{{ connectedHosts }} {{ t('dashboard.connected') }}</span>
              <span v-else>{{ t('dashboard.no_hosts') }}</span>
            </div>
          </div>
          <div class="stat-card" @click="navigateToView('topology')" style="cursor:pointer;">
            <div class="stat-label">{{ t('dashboard.apps') }}</div>
            <div class="stat-value green">{{ apps.length }}</div>
            <div class="stat-detail">
              <span v-if="appsWithUrl > 0">{{ appsWithUrl }} {{ t('dashboard.with_url') }}</span>
              <span v-else>{{ t('dashboard.no_apps') }}</span>
            </div>
          </div>
          <div class="stat-card" @click="navigateToView('operations')" style="cursor:pointer;">
            <div class="stat-label">{{ t('dashboard.operations') }}</div>
            <div class="stat-value cyan">{{ operations.length }}</div>
            <div class="stat-detail">
              <span v-if="latestOp">{{ latestOp.action }} {{ latestOp.object_type }}</span>
              <span v-else>{{ t('dashboard.no_ops') }}</span>
            </div>
          </div>
          <div class="stat-card" @click="navigateToView('operations')" style="cursor:pointer;">
            <div class="stat-label">{{ t('dashboard.freshness') }}</div>
            <div class="stat-value yellow" style="font-size:20px;">{{ dataFreshness }}</div>
            <div class="stat-detail">{{ t('dashboard.last_update') }}</div>
          </div>
        </div>

        <!-- Stale data warning -->
        <div v-if="isDataStale" class="stale-data-banner">
          <svg viewBox="0 0 16 16" fill="currentColor" style="width:16px;height:16px;flex-shrink:0;"><path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9-3a1 1 0 11-2 0 1 1 0 012 0zM8 7a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 7z"/></svg>
          <div style="flex:1;">
            <span>{{ t('dashboard.stale_hint') }}</span>
            <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
              <code style="flex:1;">agentplane infra inventory &lt;target&gt; --repo-root . --write</code>
              <button class="btn-ghost" style="font-size:11px;padding:2px 8px;" @click="copyCommand" :title="t('action.copy')">
                {{ commandCopied ? '\\u2713' : '\\uD83D\\uDCCB' }}
              </button>
            </div>
          </div>
        </div>

        <!-- Domain health cards -->
        <div v-if="Object.keys(domains).length > 0" class="domain-health-row">
          <div v-for="d in domainCards" :key="d.key" class="domain-card" @click="domainCardClick(d.key)" style="cursor:pointer;">
            <div class="domain-card-header">
              <span class="domain-card-icon">{{ d.icon }}</span>
              <span class="domain-card-name">{{ d.name }}</span>
            </div>
            <div class="domain-card-metrics">
              <div v-for="m in d.metrics" :key="m.label" class="domain-metric">
                <span class="domain-metric-value">{{ m.value }}</span>
                <span class="domain-metric-label">{{ m.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Main content grid -->
        <div class="content-grid">
          <!-- Left column -->
          <div class="content-main">
            <!-- Topology tree (inline) -->
            <div class="panel" v-if="topology.targets.length > 0">
              <div class="panel-header">
                <div class="panel-title">
                  <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8.5.75a.75.75 0 00-1.5 0v5.19L4.391 3.33a.75.75 0 10-1.06 1.061L5.939 7H.75a.75.75 0 000 1.5h5.19l-2.61 2.609a.75.75 0 101.061 1.06L7 9.561v5.189a.75.75 0 001.5 0V9.56l2.609 2.61a.75.75 0 101.06-1.061L9.561 8.5h5.189a.75.75 0 000-1.5H9.56l2.61-2.609a.75.75 0 00-1.061-1.06L8.5 5.939V.75z"/></svg>
                  {{ t('dashboard.resource_topo') }}
                </div>
                <div style="display:flex;gap:8px;align-items:center;">
                  <button class="btn-ghost btn-sm" @click="toggleAllTargets" :title="allTargetsExpanded ? t('action.collapse_all') : t('action.expand_all')" :aria-expanded="allTargetsExpanded">
                    {{ allTargetsExpanded ? t('action.collapse_all') : t('action.expand_all') }}
                  </button>
                  <span class="panel-count">{{ topology.targets.length }} {{ t('dashboard.targets') }}</span>
                </div>
              </div>
              <div class="panel-body">
                <div v-for="target in topology.targets" :key="target.target" class="topo-target">
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
            </div>

            <!-- Applications table -->
            <div class="panel" v-if="apps.length > 0">
              <div class="panel-header">
                <div class="panel-title">
                  <svg viewBox="0 0 16 16" fill="currentColor"><path d="M0 1.75A.75.75 0 01.75 1h4.253c1.227 0 2.317.59 3 1.501A3.744 3.744 0 0111.006 1h4.245a.75.75 0 01.75.75v10.5a.75.75 0 01-.75.75h-4.507a2.25 2.25 0 00-1.591.659l-.622.621a.75.75 0 01-1.06 0l-.622-.621A2.25 2.25 0 005.258 13H.75a.75.75 0 01-.75-.75V1.75zm7.251 10.324l.004-5.073-.002-2.253A2.25 2.25 0 005.003 2.5H1.5v9h3.757a3.75 3.75 0 011.994.574zM8.755 4.75l-.004 7.322a3.752 3.752 0 011.992-.572H14.5v-9h-3.495a2.25 2.25 0 00-2.25 2.25z"/></svg>
                  {{ t('dashboard.apps') }}
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                  <input v-model="appSearch" class="search-input" :placeholder="t('topology.search')" :aria-label="t('topology.search')" style="width:160px;min-width:120px;">
                  <span class="panel-count">{{ filteredApps.length }}/{{ apps.length }}</span>
                </div>
              </div>
              <div class="panel-body">
                <div v-if="filteredApps.length === 0" class="empty-state" style="padding:24px;">
                  {{ t('topology.no_match') }}
                </div>
                <table v-else class="data-table">
                  <thead>
                    <tr>
                      <th @click="toggleSort('app')" class="sortable-th" :aria-sort="sortAria('app')">App{{ sortIcon('app') }}</th>
                      <th @click="toggleSort('target')" class="sortable-th" :aria-sort="sortAria('target')">Target{{ sortIcon('target') }}</th>
                      <th>Service Key</th>
                      <th>Control Plane</th>
                      <th @click="toggleSort('public_url')" class="sortable-th" :aria-sort="sortAria('public_url')">Public URL{{ sortIcon('public_url') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="app in sortedApps" :key="app.app + app.target">
                      <td class="cell-primary">{{ app.app }}</td>
                      <td class="cell-mono">{{ app.target }}</td>
                      <td class="cell-mono">{{ app.service_key || '-' }}</td>
                      <td><span class="control-plane-tag">{{ app.control_plane || '-' }}</span></td>
                      <td>
                        <a v-if="app.public_url" :href="app.public_url" target="_blank" class="cell-link">
                          {{ truncateUrl(app.public_url) }}
                        </a>
                        <span v-else style="color:var(--fg-muted);">-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Empty states -->
            <div v-if="hosts.length === 0 && apps.length === 0" class="panel">
              <div class="empty-state">
                <div class="empty-state-icon">&#x1F5A5;</div>
                <div class="empty-state-title">{{ t('dashboard.no_resources') }}</div>
                <div class="empty-state-hint" v-html="t('dashboard.no_resources_hint')"></div>
              </div>
            </div>
          </div>

          <!-- Right column -->
          <div class="content-side">
            <!-- Host cards -->
            <div class="panel" v-if="hosts.length > 0">
              <div class="panel-header">
                <div class="panel-title">
                  <svg viewBox="0 0 16 16" fill="currentColor"><path d="M2 3.75A.75.75 0 012.75 3h10.5a.75.75 0 010 1.5H2.75A.75.75 0 012 3.75zm0 4A.75.75 0 012.75 7h10.5a.75.75 0 010 1.5H2.75A.75.75 0 012 7.75zm0 4a.75.75 0 01.75-.75h10.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75z"/></svg>
                  {{ t('dashboard.hosts_title') }}
                </div>
                <span class="panel-count">{{ hosts.length }}</span>
              </div>
              <div class="panel-body">
                <div v-for="host in hosts" :key="host.target" class="host-card" @click="selectHost(host)">
                  <div class="host-card-row">
                    <span class="status-dot" :class="host.status"></span>
                    <span class="host-name">{{ host.hostname }}</span>
                    <span class="host-ip">{{ host.ip || 'local' }}</span>
                    <button class="copy-btn" @click.stop="copyText(host.ip || host.hostname)" :title="t('action.copy')">&#x2398;</button>
                  </div>
                  <div class="host-meta">
                    <span class="host-meta-item">
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1.5a.25.25 0 00-.25.25v12.5c0 .138.112.25.25.25h12.5a.25.25 0 00.25-.25V1.75a.25.25 0 00-.25-.25H1.75zM0 1.75C0 .784.784 0 1.75 0h12.5C15.216 0 16 .784 16 1.75v12.5A1.75 1.75 0 0114.25 16H1.75A1.75 1.75 0 010 14.25V1.75z"/></svg>
                      {{ host.label }}
                    </span>
                    <span v-if="host.provider" class="host-meta-item">{{ host.provider }}</span>
                    <span v-if="host.last_seen" class="host-meta-item">{{ formatRelativeTime(host.last_seen, t) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Operations timeline -->
            <div class="panel" v-if="operations.length > 0">
              <div class="panel-header">
                <div class="panel-title">
                  <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"/></svg>
                  {{ t('dashboard.recent_ops') }}
                </div>
                <button class="btn-ghost btn-sm" @click="navigateToView('operations')">{{ t('dashboard.view_all') }}</button>
              </div>
              <div class="panel-body">
                <div v-for="op in sidebarOps" :key="op.op_id" class="op-item">
                  <span class="op-time">{{ formatRelativeTime(op.timestamp, t) }}</span>
                  <div class="op-body">
                    <div class="op-action">
                      <span class="op-target-tag">{{ op.target }}</span>
                      <span class="op-type-tag">{{ op.object_type }}</span>
                      {{ op.action }}
                    </div>
                    <div class="op-result" :class="resultBadgeClass(op.result)">{{ op.result }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- App / Host detail panel overlay -->
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
            <div v-else-if="detailPanel.error" style="color:var(--accent-red);font-size:13px;">{{ detailPanel.error }}</div>
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
    const navigateToView = Vue.inject('navigateToView', function () {});
    const { t } = useI18n();

    const hosts = ref([]);
    const apps = ref([]);
    const operations = ref([]);
    const topology = ref({ targets: [], generated_at: '' });
    const domains = ref({});
    const loading = ref(true);
    const loadError = ref('');
    const expandedTargets = ref(new Set());

    const { detailPanel, openDetail, closeDetail } = useDetailPanel(authToken);

    const connectedHosts = computed(() => hosts.value.filter(h => h.status === 'connected').length);
    const appsWithUrl = computed(() => apps.value.filter(a => a.public_url).length);
    const latestOp = computed(() => operations.value.length > 0 ? operations.value[0] : null);
    const sidebarOps = computed(() => operations.value.slice(0, 5));
    const dataFreshness = computed(() => {
      if (!latestOp.value || !latestOp.value.timestamp) return t('time.na');
      return formatRelativeTime(latestOp.value.timestamp, t);
    });

    const isDataStale = computed(() => {
      if (!latestOp.value || !latestOp.value.timestamp) return true;
      const ts = new Date(latestOp.value.timestamp);
      const now = new Date();
      const diffDays = (now - ts) / (1000 * 60 * 60 * 24);
      return diffDays > 7;
    });

    const domainCards = computed(() => {
      const d = domains.value;
      const cards = [];
      if (d.infra) {
        cards.push({
          key: 'infra', icon: '\u{1F5A5}', name: t('domain.infra'),
          metrics: [
            { value: d.infra.host_count || 0, label: t('domain.hosts') },
            { value: d.infra.total_containers || 0, label: t('domain.containers') },
            { value: d.infra.total_compose_services || 0, label: t('domain.compose') },
          ],
        });
      }
      if (d.service) {
        cards.push({
          key: 'service', icon: '\u2699', name: t('domain.service'),
          metrics: [{ value: d.service.service_count || 0, label: t('domain.services_count') }],
        });
      }
      if (d.app) {
        cards.push({
          key: 'app', icon: '\u{1F4E6}', name: t('domain.app'),
          metrics: [{ value: d.app.app_count || 0, label: t('dashboard.apps') }],
        });
      }
      if (d.ingress) {
        cards.push({
          key: 'ingress', icon: '\u{1F310}', name: t('domain.ingress'),
          metrics: [{ value: d.ingress.ingress_count || 0, label: t('domain.ingress_count') }],
        });
      }
      if (d.project) {
        const m = [{ value: d.project.targets || 0, label: t('dashboard.targets') }];
        if (d.project.public_skills != null) m.push({ value: d.project.public_skills, label: t('domain.skills') });
        if (d.project.current_phase) m.push({ value: d.project.current_phase, label: t('domain.phase') });
        cards.push({ key: 'project', icon: '\u{1F4CB}', name: t('domain.project'), metrics: m });
      }
      return cards;
    });

    // ── Sorting & Filtering ──
    const { toggleSort, sortIcon, sortAria, sortItems } = useSortable('app');
    const appSearch = ref('');
    const debouncedAppSearch = useDebounce(appSearch, 200);

    const filteredApps = computed(() => {
      const q = debouncedAppSearch.value.toLowerCase().trim();
      if (!q) return apps.value;
      return apps.value.filter(a =>
        (a.app || '').toLowerCase().includes(q) ||
        (a.target || '').toLowerCase().includes(q) ||
        (a.service_key || '').toLowerCase().includes(q) ||
        (a.control_plane || '').toLowerCase().includes(q)
      );
    });
    const sortedApps = computed(() => sortItems(filteredApps.value));

    // ── Topology expand/collapse all ──
    const allTargetsExpanded = computed(() =>
      topology.value.targets.length > 0 && topology.value.targets.every(t => expandedTargets.value.has(t.target))
    );

    function toggleAllTargets() {
      if (allTargetsExpanded.value) {
        expandedTargets.value = new Set();
      } else {
        expandedTargets.value = new Set(topology.value.targets.map(t => t.target));
      }
    }

    const commandCopied = ref(false);
    function copyCommand() {
      copyToClipboard('agentplane infra inventory <target> --repo-root . --write').then(ok => {
        if (ok) {
          commandCopied.value = true;
          showToast(t('toast.copied'), 'success', 1500);
          setTimeout(() => { commandCopied.value = false; }, 2000);
        }
      });
    }

    function copyText(text) {
      copyToClipboard(text).then(ok => {
        if (ok) showToast(t('toast.copied'), 'success', 1500);
      });
    }

    function copyDetailVal(val) {
      copyToClipboard(formatDetailVal(val)).then(ok => {
        if (ok) showToast(t('toast.copied'), 'success', 1500);
      });
    }

    async function fetchDashboard() {
      loadError.value = '';
      try {
        const res = await apiFetch('/api/dashboard', authToken);
        if (!res.ok) throw new Error(t('error.api_failed'));
        const data = await res.json();
        hosts.value = data.hosts || [];
        apps.value = data.apps || [];
        operations.value = data.operations || [];
        topology.value = data.topology || { targets: [], generated_at: '' };
        if (topology.value.targets && topology.value.targets.length > 0 && expandedTargets.value.size === 0) {
          expandedTargets.value.add(topology.value.targets[0].target);
        }
        domains.value = data.domains || {};
      } catch (e) {
        loadError.value = t('error.load_data') + ': ' + e.message;
      } finally {
        loading.value = false;
      }
    }

    useDataPoller(fetchDashboard);

    function toggleTarget(target) {
      if (expandedTargets.value.has(target)) {
        expandedTargets.value.delete(target);
      } else {
        expandedTargets.value.add(target);
      }
    }

    function selectApp(target, app) {
      openDetail(`${app.app} (${target})`, `/api/apps/${target}/${app.app}`);
    }

    function selectHost(host) {
      openDetail(`${host.hostname} (${host.target})`, `/api/servers/${host.target}`);
    }

    function domainCardClick(key) {
      var viewMap = { infra: 'topology', service: 'operations', app: 'topology', ingress: 'topology', project: 'capability-map' };
      if (viewMap[key]) navigateToView(viewMap[key]);
    }

    return {
      hosts, apps, operations, topology, domains, loading, loadError,
      expandedTargets, detailPanel,
      connectedHosts, appsWithUrl, latestOp, dataFreshness, isDataStale, domainCards, sidebarOps,
      sortedApps, filteredApps, allTargetsExpanded, appSearch,
      fetchDashboard, toggleTarget, toggleAllTargets, selectApp, selectHost, closeDetail, domainCardClick,
      formatRelativeTime, formatTimestamp, truncateUrl,
      resultBadgeClass, appStatusClass, serviceStatusClass, formatDetailVal,
      isDetailUrl, isDetailStatus, isDetailHidden, copyDetailVal,
      toggleSort, sortIcon, sortAria,
      commandCopied, copyCommand, copyText,
      navigateToView,
      t,
    };
  },
};
