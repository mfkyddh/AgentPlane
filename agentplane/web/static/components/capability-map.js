// AgentPlane — Capability Map view component
// Shows what AgentPlane can do: implemented / partial / planned capabilities

const CapabilityMapComponent = {
  template: `
    <div class="cap-map">
      <div class="cap-legend">
        <span class="cap-legend-item"><span class="cap-dot implemented"></span> {{ t('cap.legend.implemented') }}</span>
        <span class="cap-legend-item"><span class="cap-dot partial"></span> {{ t('cap.legend.partial') }}</span>
        <span class="cap-legend-item"><span class="cap-dot planned"></span> {{ t('cap.legend.planned') }}</span>
      </div>

      <div v-if="loading" class="cap-loading">{{ t('action.loading') }}</div>
      <div v-else-if="error" class="cap-error">{{ error }}</div>
      <div v-else class="cap-layers">
        <div v-for="layer in layers" :key="layer.id" class="cap-layer">
          <div class="cap-layer-header" @click="toggle(layer.id)">
            <span class="cap-toggle">{{ expanded[layer.id] ? '▼' : '▶' }}</span>
            <span class="cap-layer-name">{{ layer.name }}</span>
            <span class="cap-layer-stats">{{ layerStats(layer) }}</span>
          </div>
          <div v-if="expanded[layer.id]" class="cap-layer-body">
            <div v-for="obj in layer.objects" :key="obj.id" class="cap-object">
              <div class="cap-object-header" @click="toggle(obj.id)">
                <span class="cap-toggle">{{ expanded[obj.id] ? '▼' : '▶' }}</span>
                <span class="cap-object-name">{{ obj.name }}</span>
                <span class="cap-object-stats">{{ objectStats(obj) }}</span>
              </div>
              <div v-if="expanded[obj.id]" class="cap-object-body">
                <div v-for="cap in obj.capabilities" :key="cap.id" class="cap-item">
                  <span class="cap-dot" :class="cap.status"></span>
                  <span class="cap-item-name">{{ cap.name }}</span>
                  <code v-if="cap.cli && cap.status === 'implemented'" class="cap-cli">{{ cap.cli }}</code>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const { ref, reactive, onMounted, inject } = Vue;
    const authToken = inject('authToken', ref(''));
    const { t } = useI18n();

    const layers = ref([]);
    const loading = ref(true);
    const error = ref('');
    const expanded = reactive({});

    async function loadCapabilities() {
      try {
        const headers = {};
        if (authToken.value) {
          headers['Authorization'] = 'Bearer ' + authToken.value;
        }
        const res = await fetch('/api/capabilities', { headers });
        if (!res.ok) throw new Error(t('error.load_failed'));
        const data = await res.json();
        layers.value = data.layers || [];
        // Auto-expand first layer
        if (layers.value.length > 0) {
          expanded[layers.value[0].id] = true;
        }
      } catch (e) {
        error.value = t('cap.loading');
      } finally {
        loading.value = false;
      }
    }

    function toggle(id) {
      expanded[id] = !expanded[id];
    }

    function countByStatus(items, status) {
      return items.filter(c => c.status === status).length;
    }

    function layerStats(layer) {
      const allCaps = layer.objects.flatMap(obj => obj.capabilities);
      const impl = countByStatus(allCaps, 'implemented');
      return impl + '/' + allCaps.length;
    }

    function objectStats(obj) {
      const impl = countByStatus(obj.capabilities, 'implemented');
      return impl + '/' + obj.capabilities.length;
    }

    onMounted(loadCapabilities);

    return { layers, loading, error, expanded, toggle, layerStats, objectStats, t };
  },
};
