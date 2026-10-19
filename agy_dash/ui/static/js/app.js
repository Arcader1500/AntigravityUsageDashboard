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
})();
