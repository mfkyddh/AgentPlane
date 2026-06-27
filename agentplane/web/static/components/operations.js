// AgentPlane — Operations & Audit Log component
// Shows operation history, audit log, and provides action buttons
// Dynamic targets, sortable tables, text search

const OperationsComponent = {
  template: `
    <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; padding:20px;">
      <!-- Header -->
      <div class="panel" style="margin-bottom:20px;">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0110.25 10H7.061l-2.574 2.573A.25.25 0 014 12.354V10H1.75A1.75 1.75 0 010 8.25v-5.5C0 1.784.784 1 1.75 1z"/></svg>
            {{ t('operations.title') }}
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn-ghost" @click="refreshOps">
              <svg viewBox="0 0 16 16" fill="currentColor" style="width:14px;height:14px;"><path d="M8 2.5a5.487 5.487 0 00-4.131 1.869l1.204 1.204A.25.25 0 014.896 6H1.25A.25.25 0 011 5.75V2.104a.25.25 0 01.427-.177l1.38 1.38A7.002 7.002 0 0115 8a.75.75 0 01-1.5 0 5.5 5.5 0 00-5.5-5.5z"/></svg>
              {{ t('action.refresh') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs" style="margin-bottom:16px;">
        <button class="tab-btn" :class="{active: tab === 'history'}" @click="tab = 'history'">
          {{ t('operations.history') }}
        </button>
        <button class="tab-btn" :class="{active: tab === 'audit'}" @click="switchToAudit">
          {{ t('operations.audit') }}
        </button>
        <button class="tab-btn" :class="{active: tab === 'actions'}" @click="tab = 'actions'">
          {{ t('operations.actions') }}
        </button>
      </div>

      <!-- Operation History -->
      <div v-if="tab === 'history'" class="panel">
        <div class="panel-header" style="border-bottom:none;padding-bottom:0;">
          <div class="panel-title">{{ t('operations.history') }}</div>
          <input v-model="historySearch" class="search-input" :placeholder="t('operations.search')" :aria-label="t('operations.search')" style="width:200px;">
        </div>
        <div class="panel-body" style="padding:0;">
          <div v-if="loading" class="loading-state">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
          <div v-else-if="historyError" class="error-state">
            <div class="error-state-msg">{{ historyError }}</div>
            <button class="retry-btn" @click="refreshOps">{{ t('action.retry') }}</button>
          </div>
          <div v-else-if="filteredOps.length === 0" class="empty-state">
            {{ operations.length === 0 ? t('operations.no_history') : t('operations.no_match') }}
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th @click="opSort.toggleSort('timestamp')" class="sortable-th" :aria-sort="opSort.sortAria('timestamp')">{{ t('operations.time') }}{{ opSort.sortIcon('timestamp') }}</th>
                <th @click="opSort.toggleSort('target')" class="sortable-th" :aria-sort="opSort.sortAria('target')">{{ t('operations.target') }}{{ opSort.sortIcon('target') }}</th>
                <th @click="opSort.toggleSort('object_type')" class="sortable-th" :aria-sort="opSort.sortAria('object_type')">{{ t('operations.type') }}{{ opSort.sortIcon('object_type') }}</th>
                <th @click="opSort.toggleSort('action')" class="sortable-th" :aria-sort="opSort.sortAria('action')">{{ t('operations.action') }}{{ opSort.sortIcon('action') }}</th>
                <th @click="opSort.toggleSort('result')" class="sortable-th" :aria-sort="opSort.sortAria('result')">{{ t('operations.result') }}{{ opSort.sortIcon('result') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in sortedOps" :key="op.op_id">
                <td class="mono">{{ formatTimestamp(op.timestamp) }}</td>
                <td><span class="badge">{{ op.target }}</span></td>
                <td>{{ op.object_type }}</td>
                <td>{{ op.action }}</td>
                <td>
                  <span class="status-badge" :class="resultBadgeClass(op.result)"
                        style="cursor:pointer;" :title="t('operations.click_to_filter')"
                        @click="historySearch = op.result">
                    {{ op.result }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Audit Log -->
      <div v-if="tab === 'audit'" class="panel">
        <div class="panel-header">
          <div class="panel-title">{{ t('operations.audit_log') }}</div>
          <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <input v-model="auditSearch" class="search-input" :placeholder="t('operations.search')" :aria-label="t('operations.search')" style="width:160px;">
            <select v-model="auditTarget" class="select-sm" @change="fetchAuditLog">
              <option value="">{{ t('operations.all_targets') }}</option>
              <option v-for="tgt in targets" :key="tgt" :value="tgt">{{ tgt }}</option>
            </select>
            <select v-model.number="auditLimit" class="select-sm" @change="fetchAuditLog">
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
            <button class="btn-ghost btn-sm" @click="exportAuditLog" :title="t('operations.export')">
              &#x2B07; {{ t('operations.export') }}
            </button>
          </div>
        </div>
        <div class="panel-body" style="padding:0;">
          <div v-if="auditLoading" class="loading-state">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
          <div v-else-if="auditError" class="error-state">
            <div class="error-state-msg">{{ auditError }}</div>
            <button class="retry-btn" @click="fetchAuditLog">{{ t('action.retry') }}</button>
          </div>
          <div v-else-if="filteredAudit.length === 0" class="empty-state">
            {{ auditEntries.length === 0 ? t('operations.no_audit') : t('operations.no_match') }}
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th @click="auditSort.toggleSort('timestamp')" class="sortable-th" :aria-sort="auditSort.sortAria('timestamp')">{{ t('operations.time') }}{{ auditSort.sortIcon('timestamp') }}</th>
                <th @click="auditSort.toggleSort('command')" class="sortable-th" :aria-sort="auditSort.sortAria('command')">{{ t('operations.command') }}{{ auditSort.sortIcon('command') }}</th>
                <th @click="auditSort.toggleSort('action')" class="sortable-th" :aria-sort="auditSort.sortAria('action')">{{ t('operations.action') }}{{ auditSort.sortIcon('action') }}</th>
                <th @click="auditSort.toggleSort('target')" class="sortable-th" :aria-sort="auditSort.sortAria('target')">{{ t('operations.target') }}{{ auditSort.sortIcon('target') }}</th>
                <th>{{ t('operations.dry_run') }}</th>
                <th @click="auditSort.toggleSort('result')" class="sortable-th" :aria-sort="auditSort.sortAria('result')">{{ t('operations.result') }}{{ auditSort.sortIcon('result') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(entry, idx) in sortedAudit" :key="idx">
                <td class="mono">{{ formatTimestamp(entry.timestamp) }}</td>
                <td><span class="badge">{{ entry.command }}</span></td>
                <td>{{ entry.action }}</td>
                <td>{{ entry.target }}</td>
                <td>
                  <span v-if="entry.dry_run" class="badge badge-warning">DRY</span>
                  <span v-else class="badge badge-success">LIVE</span>
                </td>
                <td>
                  <span class="status-badge" :class="resultBadgeClass(entry.result)"
                        style="cursor:pointer;" :title="t('operations.click_to_filter')"
                        @click="auditSearch = entry.result">
                    {{ entry.result }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Quick Actions -->
      <div v-if="tab === 'actions'" class="panel">
        <div class="panel-header">
          <div class="panel-title">{{ t('operations.quick_actions') }}</div>
        </div>
        <div class="panel-body">
          <div class="actions-grid">
            <!-- Service Actions -->
            <div class="action-group">
              <h4>{{ t('operations.service_actions') }}</h4>
              <div class="action-form">
                <select v-model="serviceTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') }}</option>
                  <option v-for="tgt in targets" :key="tgt" :value="tgt">{{ tgt }}</option>
                </select>
                <input v-model="serviceName" class="form-input" :placeholder="t('operations.service_name')">
                <div class="action-buttons">
                  <button class="btn btn-primary" @click="servicePlan" :disabled="!serviceTarget || !serviceName || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.plan') }}
                  </button>
                  <button class="btn btn-success" @click="serviceVerify" :disabled="!serviceTarget || !serviceName || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.verify') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- App Deploy Actions -->
            <div class="action-group">
              <h4>{{ t('operations.app_deploy') }}</h4>
              <div class="action-form">
                <select v-model="deployTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') }}</option>
                  <option v-for="tgt in targets" :key="tgt" :value="tgt">{{ tgt }}</option>
                </select>
                <input v-model="deployApp" class="form-input" :placeholder="t('operations.app_name')">
                <div class="action-buttons">
                  <button class="btn btn-warning" @click="appDeploy(false)" :disabled="!deployTarget || !deployApp || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.deploy_dry') }}
                  </button>
                  <button class="btn btn-danger" @click="appDeploy(true)" :disabled="!deployTarget || !deployApp || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.deploy') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- App Rollback Actions -->
            <div class="action-group">
              <h4>{{ t('operations.app_rollback') }}</h4>
              <div class="action-form">
                <select v-model="rollbackTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') }}</option>
                  <option v-for="tgt in targets" :key="tgt" :value="tgt">{{ tgt }}</option>
                </select>
                <input v-model="rollbackApp" class="form-input" :placeholder="t('operations.app_name')">
                <div class="action-buttons">
                  <button class="btn btn-warning" @click="appRollback(false)" :disabled="!rollbackTarget || !rollbackApp || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.rollback_dry') }}
                  </button>
                  <button class="btn btn-danger" @click="appRollback(true)" :disabled="!rollbackTarget || !rollbackApp || actionLoading">
                    {{ actionLoading ? t('action.loading') : t('operations.rollback') }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Action Result -->
          <div v-if="actionResult" class="action-result" :class="actionResult.ok ? 'success' : 'error'">
            <pre>{{ JSON.stringify(actionResult, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const { t } = useI18n();
    const authToken = Vue.inject('authToken', Vue.ref(''));

    const tab = ref('history');
    const loading = ref(false);
    const auditLoading = ref(false);
    const historyError = ref('');
    const auditError = ref('');
    const operations = ref([]);
    const auditEntries = ref([]);
    const targets = ref([]);
    const auditTarget = ref('');
    const auditLimit = ref(100);

    // Search
    const historySearch = ref('');
    const auditSearch = ref('');
    const debouncedHistorySearch = useDebounce(historySearch, 200);
    const debouncedAuditSearch = useDebounce(auditSearch, 200);

    // Sorting
    const opSort = useSortable('timestamp', 'desc');
    const auditSort = useSortable('timestamp', 'desc');

    // Action form state
    const serviceTarget = ref('');
    const serviceName = ref('');
    const deployTarget = ref('');
    const deployApp = ref('');
    const rollbackTarget = ref('');
    const rollbackApp = ref('');
    const actionResult = ref(null);
    const actionLoading = ref(false);

    // ── Dynamic targets from hosts API ──
    async function fetchTargets() {
      targets.value = await fetchTargetList(authToken);
    }

    // ── Filtered & sorted ops ──
    const filteredOps = computed(() => {
      const q = debouncedHistorySearch.value.toLowerCase().trim();
      if (!q) return operations.value;
      return operations.value.filter(op =>
        (op.target || '').toLowerCase().includes(q) ||
        (op.object_type || '').toLowerCase().includes(q) ||
        (op.action || '').toLowerCase().includes(q) ||
        (op.result || '').toLowerCase().includes(q)
      );
    });

    const sortedOps = computed(() => opSort.sortItems(filteredOps.value));

    const filteredAudit = computed(() => {
      const q = debouncedAuditSearch.value.toLowerCase().trim();
      if (!q) return auditEntries.value;
      return auditEntries.value.filter(e =>
        (e.command || '').toLowerCase().includes(q) ||
        (e.action || '').toLowerCase().includes(q) ||
        (e.target || '').toLowerCase().includes(q) ||
        (e.result || '').toLowerCase().includes(q)
      );
    });

    const sortedAudit = computed(() => auditSort.sortItems(filteredAudit.value));

    async function refreshOps() {
      loading.value = true;
      historyError.value = '';
      try {
        const [opsRes] = await Promise.all([
          apiFetch('/api/operations', authToken),
          fetchTargets(),
        ]);
        if (!opsRes.ok) throw new Error('HTTP ' + opsRes.status);
        const data = await opsRes.json();
        operations.value = data.operations || [];
      } catch (e) {
        historyError.value = t('error.load_failed') + ': ' + e.message;
        showToast(t('error.load_failed'), 'error', 3000);
      } finally {
        loading.value = false;
      }
    }

    function switchToAudit() {
      tab.value = 'audit';
      if (auditEntries.value.length === 0) fetchAuditLog();
    }

    async function fetchAuditLog() {
      auditLoading.value = true;
      auditError.value = '';
      try {
        let url = '/api/audit-log?limit=' + auditLimit.value;
        if (auditTarget.value) url += '&target=' + auditTarget.value;
        const res = await apiFetch(url, authToken);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        auditEntries.value = data.entries || [];
      } catch (e) {
        auditError.value = t('error.load_failed') + ': ' + e.message;
        showToast(t('error.load_failed'), 'error', 3000);
      } finally {
        auditLoading.value = false;
      }
    }

    async function servicePlan() {
      actionResult.value = null;
      actionLoading.value = true;
      try {
        const res = await apiFetch('/api/service/plan', authToken, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: serviceTarget.value, name: serviceName.value, operation: 'restart' })
        });
        actionResult.value = await res.json();
        showToast(t('operations.plan') + ' ' + (actionResult.value.ok ? t('operations.success') : t('operations.failed')), actionResult.value.ok ? 'success' : 'error', 3000);
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
        showToast(e.message, 'error', 3000);
      } finally {
        actionLoading.value = false;
      }
    }

    async function serviceVerify() {
      actionResult.value = null;
      actionLoading.value = true;
      try {
        const res = await apiFetch('/api/service/verify', authToken, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: serviceTarget.value, name: serviceName.value })
        });
        actionResult.value = await res.json();
        showToast(t('operations.verify') + ' ' + (actionResult.value.ok ? t('operations.success') : t('operations.failed')), actionResult.value.ok ? 'success' : 'error', 3000);
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
        showToast(e.message, 'error', 3000);
      } finally {
        actionLoading.value = false;
      }
    }

    async function appDeploy(execute) {
      if (execute && !confirm(t('operations.confirm_deploy'))) return;
      actionResult.value = null;
      actionLoading.value = true;
      try {
        const res = await apiFetch('/api/app/delivery/deploy', authToken, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: deployTarget.value, app: deployApp.value, execute: execute })
        });
        actionResult.value = await res.json();
        showToast(t('operations.app_deploy') + ' ' + (actionResult.value.ok ? t('operations.success') : t('operations.failed')), actionResult.value.ok ? 'success' : 'error', 3000);
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
        showToast(e.message, 'error', 3000);
      } finally {
        actionLoading.value = false;
      }
    }

    async function appRollback(execute) {
      if (execute && !confirm(t('operations.confirm_rollback'))) return;
      actionResult.value = null;
      actionLoading.value = true;
      try {
        const res = await apiFetch('/api/app/delivery/rollback', authToken, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: rollbackTarget.value, app: rollbackApp.value, execute: execute })
        });
        actionResult.value = await res.json();
        showToast(t('operations.app_rollback') + ' ' + (actionResult.value.ok ? t('operations.success') : t('operations.failed')), actionResult.value.ok ? 'success' : 'error', 3000);
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
        showToast(e.message, 'error', 3000);
      } finally {
        actionLoading.value = false;
      }
    }

    function exportAuditLog() {
      var url = '/api/audit-log/export?limit=' + auditLimit.value;
      if (auditTarget.value) url += '&target=' + auditTarget.value;
      var headers = {};
      if (authToken && authToken.value) {
        headers['Authorization'] = 'Bearer ' + authToken.value;
      }
      fetch(url, { headers: headers }).then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.blob();
      }).then(function (blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'audit-log.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
        showToast(t('operations.export_success'), 'success', 2000);
      }).catch(function (e) {
        showToast(t('operations.export_failed'), 'error', 3000);
      });
    }

    useDataPoller(() => {
      if (tab.value === 'history' || operations.value.length === 0) {
        refreshOps();
      }
      if (tab.value === 'audit') {
        fetchAuditLog();
      }
    });

    return {
      tab, loading, auditLoading, historyError, auditError, operations, auditEntries, targets,
      auditTarget, auditLimit, serviceTarget, serviceName,
      deployTarget, deployApp, rollbackTarget, rollbackApp,
      actionResult, actionLoading, refreshOps, fetchAuditLog, exportAuditLog, formatTimestamp, resultBadgeClass,
      servicePlan, serviceVerify, appDeploy, appRollback, t,
      historySearch, auditSearch,
      filteredOps, sortedOps, filteredAudit, sortedAudit,
      opSort, auditSort, switchToAudit, showToast,
    };
  }
};
