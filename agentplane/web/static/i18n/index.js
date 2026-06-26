// AgentPlane — i18n composable
// Provides useI18n() with locale switching and t() translation function

const _i18nState = Vue.reactive({
  locale: localStorage.getItem('ap-locale') || 'zh',
  messages: {},
  loaded: false,
});

async function _loadLocale(locale) {
  if (_i18nState.messages[locale]) return _i18nState.messages[locale];
  try {
    const res = await fetch('/static/i18n/' + locale + '.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('Failed to load ' + locale);
    _i18nState.messages[locale] = await res.json();
    return _i18nState.messages[locale];
  } catch (e) {
    console.warn('[i18n] Failed to load locale:', locale, e);
    return {};
  }
}

async function _ensureLoaded() {
  if (_i18nState.loaded) return;
  await _loadLocale('zh');
  await _loadLocale('en');
  _i18nState.loaded = true;
}

function useI18n() {
  const locale = Vue.computed(() => _i18nState.locale);

  function t(key, fallback) {
    const msgs = _i18nState.messages[_i18nState.locale] || {};
    return msgs[key] || fallback || key;
  }

  async function toggleLocale() {
    const next = _i18nState.locale === 'zh' ? 'en' : 'zh';
    await _loadLocale(next);
    _i18nState.locale = next;
    localStorage.setItem('ap-locale', next);
  }

  function setLocale(loc) {
    _loadLocale(loc).then(() => {
      _i18nState.locale = loc;
      localStorage.setItem('ap-locale', loc);
    });
  }

  return { locale, t, toggleLocale, setLocale };
}

// Auto-load on import
_ensureLoaded();
