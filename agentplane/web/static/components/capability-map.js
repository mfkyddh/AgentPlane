// AgentPlane — Capability Map view component
// Shows what AgentPlane can do: implemented / partial / planned capabilities
// Supports expand/collapse all, search filtering

const CapabilityMapComponent = {
  template: `
    <div class="cap-map">
      <!-- Header with legend and controls -->
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:16px;">
        <div class="cap-legend">
          <span class="cap-legend-item"><span class="cap-dot implemented"></span> {{ t('cap.legend.implemented') }}</span>
          <span class="cap-legend-item"><span class="cap-dot partial"></span> {{ t('cap.legend.partial') }}</span>
          <span class="cap-legend-item"><span class="cap-dot planned"></span> {{ t('cap.legend.planned') }}</span>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <input v-model="searchQuery" class="search-input" :placeholder="t('cap.search')" :aria-label="t('cap.search')">
          <button class="btn-ghost" @click="toggleAll" :disabled="layers.length === 0">
            {{ allExpanded ? t('action.collapse_all') : t('action.expand_all') }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="cap-loading">{{ t('action.loading') }}</div>
      <div v-else-if="error" class="cap-error">{{ error }}</div>
      <div v-else-if="filteredLayers.length === 0" class="cap-error">{{ t('cap.no_match') }}</div>
      <div v-else class="cap-layers">
        <div v-for="layer in filteredLayers" :key="layer.id" class="cap-layer">
          <div class="cap-layer-header" @click="toggle(layer.id)">
            <span class="cap-toggle">{{ expanded[layer.id] ? '\u25BC' : '\u25B6' }}</span>
            <span class="cap-domain-icon">{{ domainIcon(layer.id) }}</span>
            <span class="cap-layer-name">
              {{ locale === 'zh' ? layer.name : layer.name_en }}
              <span v-if="locale === 'zh'" class="cap-layer-sub">{{ layer.name_en }}</span>
            </span>
            <span class="cap-layer-stats">{{ layerStats(layer) }}</span>
          </div>
          <div v-if="expanded[layer.id]" class="cap-layer-body">
            <div v-for="obj in layer.objects" :key="obj.id" class="cap-object">
              <div class="cap-object-header" @click="toggle(obj.id)">
                <span class="cap-toggle">{{ expanded[obj.id] ? '\u25BC' : '\u25B6' }}</span>
                <span class="cap-object-name">{{ locale === 'zh' ? obj.name : (obj.name_en || obj.name) }}</span>
                <span class="cap-object-stats">{{ objectStats(obj) }}</span>
              </div>
              <div v-if="expanded[obj.id]" class="cap-object-body">
                <div v-for="cap in obj.capabilities" :key="cap.id" class="cap-item">
                  <span class="cap-dot" :class="cap.status"></span>
                  <span class="cap-item-name">{{ locale === 'zh' ? cap.name : (cap.name_en || cap.name) }}</span>
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
    const { ref, reactive, computed, inject } = Vue;
    const authToken = inject('authToken', ref(''));
    const { t, locale } = useI18n();

    const domainIcons = { infra: '\u{1F5A5}', service: '\u2699', app: '\u{1F4E6}', ingress: '\u{1F310}', project: '\u{1F4CB}' };
    function domainIcon(id) { return domainIcons[id] || ''; }

    const layers = ref([]);
    const loading = ref(true);
    const error = ref('');
    const expanded = reactive({});
    const searchQuery = ref('');
    const debouncedSearch = useDebounce(searchQuery, 200);
    const filteredLayers = ref([]);

    // Watch debounced search to trigger filtering
    Vue.watch(debouncedSearch, filterLayers);

    const allExpanded = computed(() =>
      layers.value.length > 0 && layers.value.every(l => expanded[l.id])
    );

    function filterLayers() {
      const q = searchQuery.value.toLowerCase().trim();
      if (!q) {
        filteredLayers.value = layers.value;
        return;
      }
      filteredLayers.value = layers.value.filter(layer => {
        const layerMatch = (layer.name || '').toLowerCase().includes(q) ||
                          (layer.name_en || '').toLowerCase().includes(q);
        if (layerMatch) return true;
        return layer.objects.some(obj => {
          const objMatch = (obj.name || '').toLowerCase().includes(q) ||
                          (obj.name_en || '').toLowerCase().includes(q);
          if (objMatch) return true;
          return obj.capabilities.some(cap =>
            (cap.name || '').toLowerCase().includes(q) ||
            (cap.name_en || '').toLowerCase().includes(q) ||
            (cap.cli || '').toLowerCase().includes(q)
          );
        });
      });
      // Auto-expand matched layers
      filteredLayers.value.forEach(l => { expanded[l.id] = true; });
    }

    async function loadCapabilities() {
      try {
        const res = await apiFetch('/api/capabilities', authToken);
        if (!res.ok) throw new Error(t('error.load_failed'));
        const data = await res.json();
        layers.value = data.layers || [];
        if (layers.value.length > 0 && Object.keys(expanded).length === 0) {
          expanded[layers.value[0].id] = true;
        }
        filterLayers();
      } catch (e) {
        error.value = t('cap.loading');
      } finally {
        loading.value = false;
      }
    }

    function toggle(id) {
      expanded[id] = !expanded[id];
    }

    function toggleAll() {
      if (allExpanded.value) {
        layers.value.forEach(l => { expanded[l.id] = false; });
      } else {
        layers.value.forEach(l => { expanded[l.id] = true; });
      }
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

    useDataPoller(loadCapabilities);

    return { layers, loading, error, expanded, toggle, toggleAll, layerStats, objectStats, t, locale, domainIcon,
             searchQuery, filteredLayers, allExpanded, filterLayers };
  },
};
