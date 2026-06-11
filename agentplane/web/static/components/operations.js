// AgentPlane — Operations & Audit Log component
// Shows operation history, audit log, and provides action buttons

const OperationsComponent = {
  template: `
    <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; padding:20px;">
      <!-- Header -->
      <div class="panel" style="margin-bottom:20px;">
        <div class="panel-header">
          <div class="panel-title">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.75 1h8.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0110.25 10H7.061l-2.574 2.573A.25.25 0 014 12.354V10H1.75A1.75 1.75 0 010 8.25v-5.5C0 1.784.784 1 1.75 1z"/></svg>
            {{ t('operations.title') || 'Operations' }}
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn-ghost" @click="refreshOps">
              <svg viewBox="0 0 16 16" fill="currentColor" style="width:14px;height:14px;"><path d="M8 2.5a5.487 5.487 0 00-4.131 1.869l1.204 1.204A.25.25 0 014.896 6H1.25A.25.25 0 011 5.75V2.104a.25.25 0 01.427-.177l1.38 1.38A7.002 7.002 0 0115 8a.75.75 0 01-1.5 0 5.5 5.5 0 00-5.5-5.5z"/></svg>
              {{ t('action.refresh') || 'Refresh' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs" style="margin-bottom:16px;">
        <button class="tab-btn" :class="{active: tab === 'history'}" @click="tab = 'history'">
          {{ t('operations.history') || 'Operation History' }}
        </button>
        <button class="tab-btn" :class="{active: tab === 'audit'}" @click="tab = 'audit'">
          {{ t('operations.audit') || 'Audit Log' }}
        </button>
        <button class="tab-btn" :class="{active: tab === 'actions'}" @click="tab = 'actions'">
          {{ t('operations.actions') || 'Quick Actions' }}
        </button>
      </div>

      <!-- Operation History -->
      <div v-if="tab === 'history'" class="panel">
        <div class="panel-body" style="padding:0;">
          <div v-if="loading" class="loading-state">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
          <div v-else-if="operations.length === 0" class="empty-state">
            {{ t('operations.no_history') || 'No operations recorded yet' }}
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>{{ t('operations.time') || 'Time' }}</th>
                <th>{{ t('operations.target') || 'Target' }}</th>
                <th>{{ t('operations.type') || 'Type' }}</th>
                <th>{{ t('operations.action') || 'Action' }}</th>
                <th>{{ t('operations.result') || 'Result' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in operations" :key="op.op_id">
                <td class="mono">{{ formatTime(op.timestamp) }}</td>
                <td><span class="badge">{{ op.target }}</span></td>
                <td>{{ op.object_type }}</td>
                <td>{{ op.action }}</td>
                <td>
                  <span class="status-badge" :class="op.result === 'pass' ? 'success' : 'error'">
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
          <div class="panel-title">{{ t('operations.audit_log') || 'Audit Log' }}</div>
          <div style="display:flex; gap:8px; align-items:center;">
            <select v-model="auditTarget" class="select-sm" @change="fetchAuditLog">
              <option value="">{{ t('operations.all_targets') || 'All Targets' }}</option>
              <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
            </select>
            <select v-model.number="auditLimit" class="select-sm" @change="fetchAuditLog">
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
          </div>
        </div>
        <div class="panel-body" style="padding:0;">
          <div v-if="auditLoading" class="loading-state">
            <div class="skeleton skeleton-line w60"></div>
            <div class="skeleton skeleton-line w80"></div>
          </div>
          <div v-else-if="auditEntries.length === 0" class="empty-state">
            {{ t('operations.no_audit') || 'No audit entries found' }}
          </div>
          <table v-else class="data-table">
            <thead>
              <tr>
                <th>{{ t('operations.time') || 'Time' }}</th>
                <th>{{ t('operations.command') || 'Command' }}</th>
                <th>{{ t('operations.action') || 'Action' }}</th>
                <th>{{ t('operations.target') || 'Target' }}</th>
                <th>{{ t('operations.dry_run') || 'Dry Run' }}</th>
                <th>{{ t('operations.result') || 'Result' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(entry, idx) in auditEntries" :key="idx">
                <td class="mono">{{ formatTime(entry.timestamp) }}</td>
                <td><span class="badge">{{ entry.command }}</span></td>
                <td>{{ entry.action }}</td>
                <td>{{ entry.target }}</td>
                <td>
                  <span v-if="entry.dry_run" class="badge badge-warning">DRY</span>
                  <span v-else class="badge badge-success">LIVE</span>
                </td>
                <td>
                  <span class="status-badge" :class="entry.result === 'pass' ? 'success' : 'error'">
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
          <div class="panel-title">{{ t('operations.quick_actions') || 'Quick Actions' }}</div>
        </div>
        <div class="panel-body">
          <div class="actions-grid">
            <!-- Service Actions -->
            <div class="action-group">
              <h4>{{ t('operations.service_actions') || 'Service Actions' }}</h4>
              <div class="action-form">
                <select v-model="serviceTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') || 'Select Target' }}</option>
                  <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
                </select>
                <input v-model="serviceName" class="form-input" :placeholder="t('operations.service_name') || 'Service Name'">
                <div class="action-buttons">
                  <button class="btn btn-primary" @click="servicePlan" :disabled="!serviceTarget || !serviceName">
                    {{ t('operations.plan') || 'Plan' }}
                  </button>
                  <button class="btn btn-success" @click="serviceVerify" :disabled="!serviceTarget || !serviceName">
                    {{ t('operations.verify') || 'Verify' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- App Deploy Actions -->
            <div class="action-group">
              <h4>{{ t('operations.app_deploy') || 'App Deployment' }}</h4>
              <div class="action-form">
                <select v-model="deployTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') || 'Select Target' }}</option>
                  <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
                </select>
                <input v-model="deployApp" class="form-input" :placeholder="t('operations.app_name') || 'App Name'">
                <div class="action-buttons">
                  <button class="btn btn-warning" @click="appDeploy(false)" :disabled="!deployTarget || !deployApp">
                    {{ t('operations.deploy_dry') || 'Deploy (Dry Run)' }}
                  </button>
                  <button class="btn btn-danger" @click="appDeploy(true)" :disabled="!deployTarget || !deployApp">
                    {{ t('operations.deploy') || 'Deploy' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- App Rollback Actions -->
            <div class="action-group">
              <h4>{{ t('operations.app_rollback') || 'App Rollback' }}</h4>
              <div class="action-form">
                <select v-model="rollbackTarget" class="form-select">
                  <option value="">{{ t('operations.select_target') || 'Select Target' }}</option>
                  <option v-for="t in targets" :key="t" :value="t">{{ t }}</option>
                </select>
                <input v-model="rollbackApp" class="form-input" :placeholder="t('operations.app_name') || 'App Name'">
                <div class="action-buttons">
                  <button class="btn btn-warning" @click="appRollback(false)" :disabled="!rollbackTarget || !rollbackApp">
                    {{ t('operations.rollback_dry') || 'Rollback (Dry Run)' }}
                  </button>
                  <button class="btn btn-danger" @click="appRollback(true)" :disabled="!rollbackTarget || !rollbackApp">
                    {{ t('operations.rollback') || 'Rollback' }}
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
    const { t } = inject('i18n');
    const authToken = inject('authToken');
    
    const tab = ref('history');
    const loading = ref(false);
    const auditLoading = ref(false);
    const operations = ref([]);
    const auditEntries = ref([]);
    const targets = ref(['prod0-main', 'wsl']);
    const auditTarget = ref('');
    const auditLimit = ref(100);
    
    // Action form state
    const serviceTarget = ref('');
    const serviceName = ref('');
    const deployTarget = ref('');
    const deployApp = ref('');
    const rollbackTarget = ref('');
    const rollbackApp = ref('');
    const actionResult = ref(null);

    function apiFetch(url, options = {}) {
      const headers = { ...options.headers };
      if (authToken.value) {
        headers['Authorization'] = `Bearer ${authToken.value}`;
      }
      return fetch(url, { ...options, headers });
    }

    async function refreshOps() {
      loading.value = true;
      try {
        const res = await apiFetch('/api/operations');
        const data = await res.json();
        operations.value = data.operations || [];
      } catch (e) {
        console.error('Failed to fetch operations:', e);
      } finally {
        loading.value = false;
      }
    }

    async function fetchAuditLog() {
      auditLoading.value = true;
      try {
        let url = '/api/audit-log?limit=' + auditLimit.value;
        if (auditTarget.value) url += '&target=' + auditTarget.value;
        const res = await apiFetch(url);
        const data = await res.json();
        auditEntries.value = data.entries || [];
      } catch (e) {
        console.error('Failed to fetch audit log:', e);
      } finally {
        auditLoading.value = false;
      }
    }

    function formatTime(ts) {
      if (!ts) return '-';
      try {
        const d = new Date(ts);
        return d.toLocaleString();
      } catch {
        return ts;
      }
    }

    async function servicePlan() {
      actionResult.value = null;
      try {
        const res = await apiFetch('/api/service/plan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: serviceTarget.value,
            name: serviceName.value,
            operation: 'restart'
          })
        });
        actionResult.value = await res.json();
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
      }
    }

    async function serviceVerify() {
      actionResult.value = null;
      try {
        const res = await apiFetch('/api/service/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: serviceTarget.value,
            name: serviceName.value
          })
        });
        actionResult.value = await res.json();
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
      }
    }

    async function appDeploy(execute) {
      actionResult.value = null;
      try {
        const res = await apiFetch('/api/app/delivery/deploy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: deployTarget.value,
            app: deployApp.value,
            execute: execute
          })
        });
        actionResult.value = await res.json();
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
      }
    }

    async function appRollback(execute) {
      actionResult.value = null;
      try {
        const res = await apiFetch('/api/app/delivery/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: rollbackTarget.value,
            app: rollbackApp.value,
            execute: execute
          })
        });
        actionResult.value = await res.json();
      } catch (e) {
        actionResult.value = { ok: false, error: e.message };
      }
    }

    onMounted(() => {
      refreshOps();
      fetchAuditLog();
    });

    return {
      tab, loading, auditLoading, operations, auditEntries, targets,
      auditTarget, auditLimit, serviceTarget, serviceName,
      deployTarget, deployApp, rollbackTarget, rollbackApp,
      actionResult, refreshOps, fetchAuditLog, formatTime,
      servicePlan, serviceVerify, appDeploy, appRollback, t
    };
  }
};
