// High-Craft Mission Telemetry Client Runtime
(function() {
  'use strict';

  // 1. Chart hydration & memory management with ResizeObserver
  const chartObservers = new WeakMap();

  window.initCharts = function(root = document) {
    if (typeof echarts === 'undefined') return;
    const containers = root.querySelectorAll('[data-chart]');
    containers.forEach(el => {
      const scriptId = el.getAttribute('data-chart');
      const script = document.getElementById(scriptId);
      if (!script) return;
      try {
        const option = JSON.parse(script.textContent);
        let chart = echarts.getInstanceByDom(el);
        if (chart) {
          chart.dispose();
        }
        chart = echarts.init(el, null, { renderer: 'canvas' });
        chart.setOption(option, true);

        // ResizeObserver ensures chart renders perfectly at container dimensions
        if (typeof ResizeObserver !== 'undefined' && !chartObservers.has(el)) {
          const ro = new ResizeObserver(() => {
            if (chart && !chart.isDisposed()) {
              chart.resize();
            }
          });
          ro.observe(el);
          chartObservers.set(el, ro);
        }
      } catch (err) {
        console.error('Failed to parse or render chart option for', scriptId, err);
      }
    });
  };

  // Window resize fallback
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      document.querySelectorAll('[data-chart]').forEach(el => {
        const chart = echarts.getInstanceByDom(el);
        if (chart) chart.resize();
      });
    }, 100);
  });

  // 2. Drawer management
  window.openDrawer = function(id) {
    const d = document.getElementById(id);
    const b = document.getElementById('drawer-backdrop');
    if (d && b) {
      d.classList.add('open');
      b.classList.add('open');
    }
  };

  window.closeDrawers = function() {
    document.querySelectorAll('.drawer').forEach(d => d.classList.remove('open'));
    const b = document.getElementById('drawer-backdrop');
    if (b) b.classList.remove('open');
  };

  // 3. Theme toggling with cookie persistence
  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('agy_theme', next);
    document.cookie = `agy_theme=${next}; path=/; max-age=31536000`;
    const themeInput = document.getElementById('global-theme-input');
    if (themeInput) themeInput.value = next;
    const form = document.getElementById('global-filter-form');
    if (form) form.requestSubmit();
  };

  // 4. View and tab synchronization
  function syncActiveTab(targetView) {
    const urlParams = new URLSearchParams(window.location.search);
    const view = targetView || urlParams.get('view') || 'command';
    document.querySelectorAll('.nav-tab').forEach(tab => {
      if (tab.getAttribute('data-view') === view) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });
    const viewInput = document.getElementById('global-view-input');
    if (viewInput) {
      viewInput.value = view;
    }
  }

  // 5. HTMX lifecycle hooks
  document.addEventListener('DOMContentLoaded', () => {
    window.initCharts(document);
    syncActiveTab();
  });

  document.addEventListener('htmx:afterSwap', (evt) => {
    const target = evt.detail.target;
    if (target) {
      const root = document.contains(target) ? target : document;
      requestAnimationFrame(() => {
        window.initCharts(root);
      });
      syncActiveTab();
    }
  });

  // 6. Filter deck toggle
  window.toggleFilterDeck = function() {
    const deck = document.getElementById('global-filter-deck');
    if (!deck) return;
    deck.classList.toggle('open');
    const toggle = document.getElementById('filter-deck-toggle');
    if (toggle) {
      const open = deck.classList.contains('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      deck.setAttribute('aria-hidden', open ? 'false' : 'true');
    }
  };

  // 7. Progressive-disclosure sub-tabs
  // Scoped to buttons carrying data-subtab-target so the economics switcher
  // (data-econ-stage) and drawer tabs (.drawer-tab-btn) stay untouched.
  document.addEventListener('click', (evt) => {
    const btn = evt.target.closest('.subtab-btn');
    if (!btn || !btn.dataset.subtabTarget) return;

    const targetId = btn.dataset.subtabTarget;
    const bar = btn.closest('.subtab-bar') || document;
    bar.querySelectorAll('.subtab-btn').forEach(b => {
      const isActive = b === btn;
      b.classList.toggle('active', isActive);
      b.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    const pane = document.getElementById(targetId);
    document.querySelectorAll('.subtab-pane').forEach(p => {
      const isActive = p === pane;
      p.classList.toggle('active', isActive);
      p.style.display = isActive ? '' : 'none';
    });

    if (pane && typeof echarts !== 'undefined') {
      pane.querySelectorAll('[data-chart]').forEach(el => {
        const chart = echarts.getInstanceByDom(el);
        if (chart) chart.resize();
      });
    }
  });

  // 8. Drawer tab switching
  window.switchDrawerTab = function(btn, targetId) {
    const bar = btn.closest('.drawer-tab-bar');
    if (bar) bar.querySelectorAll('.subtab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const scope = document.getElementById('session-drawer-content') || document;
    scope.querySelectorAll('.drawer-tab-pane').forEach(p => {
      p.classList.toggle('active', p.id === targetId);
      if (!p.classList.contains('active')) p.style.display = 'none';
    });
    const target = scope.querySelector('#' + targetId);
    if (target) {
      target.style.display = '';
      target.classList.add('active');
    }
  };

  // 9. Escape closes drawers and the filter deck
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      window.closeDrawers();
      const deck = document.getElementById('global-filter-deck');
      if (deck && deck.classList.contains('open')) window.toggleFilterDeck();
    }
  });
})();
