/* Preload displayed images plus hidden dossiers and both illustrated maps. */
(() => {
  'use strict';
  async function prepareImages() {
    const loader = document.getElementById('site-loader');
    if (!loader || !document.documentElement.classList.contains('is-loading')) return;
    const started = performance.now();
    const urls = new Set();
    const add = value => {
      if (typeof value !== 'string' || !value.trim()) return;
      const url = new URL(value.trim(), document.baseURI);
      if (['http:', 'https:', 'data:'].includes(url.protocol)) urls.add(url.href);
    };
    const scanData = value => {
      if (Array.isArray(value)) { value.forEach(scanData); return; }
      if (!value || typeof value !== 'object') return;
      for (const [key, item] of Object.entries(value)) {
        if (['image', 'indexImage', 'emblem'].includes(key)) add(item);
        else if (item && typeof item === 'object') scanData(item);
      }
    };
    if (typeof ALTINEL_DATA !== 'undefined') scanData(ALTINEL_DATA);
    document.querySelectorAll('img').forEach(img => {
      img.loading = 'eager';
      add(img.currentSrc || img.src);
    });
    document.querySelectorAll('svg image').forEach(img => add(img.getAttribute('href')));
    // The second map is created on demand, so include its image before opening.
    add('assets/campus-illustrated.webp');
    add('assets/world-parchment.webp');
    const scanRules = rules => {
      for (const rule of rules) {
        if (rule.type === CSSRule.FONT_FACE_RULE) continue; // Fonts are not image resources.
        if (rule.style) {
          const pattern = /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)/g;
          for (const match of rule.style.cssText.matchAll(pattern)) add(match[1] || match[2] || match[3]);
        }
        if (rule.cssRules) scanRules(rule.cssRules);
      }
    };
    for (const sheet of document.styleSheets) {
      try { scanRules(sheet.cssRules); }
      catch (error) { /* Cross-origin stylesheets may not expose their rules. */ }
    }
    const sources = [...urls];
    const bar = loader.querySelector('[role="progressbar"]');
    const fill = loader.querySelector('.site-loader-fill');
    const label = loader.querySelector('.site-loader-percent');
    let completed = 0;
    let failed = 0;
    let next = 0;
    loader.dataset.total = String(sources.length);
    const update = () => {
      const percent = sources.length ? Math.floor(completed / sources.length * 100) : 100;
      bar.setAttribute('aria-valuenow', String(percent));
      fill.style.transform = `scaleX(${percent / 100})`;
      label.textContent = `${percent}%`;
    };
    const load = src => new Promise(resolve => {
      const image = new Image();
      image.decoding = 'async';
      let settled = false;
      const finish = success => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        image.onload = image.onerror = null;
        if (!success) failed++;
        completed++;
        update();
        resolve();
      };
      const timer = setTimeout(() => { finish(false); image.src = ''; }, 20000);
      image.onerror = () => finish(false);
      image.onload = async () => {
        try { await image.decode(); finish(true); }
        catch (error) { finish(false); }
      };
      image.src = src;
    });
    const worker = async () => {
      while (next < sources.length && document.documentElement.classList.contains('is-loading')) {
        await load(sources[next++]);
      }
    };
    try {
      update();
      const fontsReady = document.fonts ? new Promise(resolve => {
        const timer = setTimeout(resolve, 8000);
        document.fonts.ready.then(() => { clearTimeout(timer); resolve(); }, () => { clearTimeout(timer); resolve(); });
      }) : Promise.resolve();
      await Promise.all([fontsReady, ...Array.from({length: Math.min(6, sources.length)}, worker)]);
      loader.dataset.failed = String(failed);
      if (!document.documentElement.classList.contains('is-loading')) return;
      loader.querySelector('[role="status"]').textContent = '열람 준비 완료';
      // Give the final progress update a paint before the navy curtain fades away.
      await new Promise(resolve => setTimeout(resolve, Math.max(180, 600 - (performance.now() - started))));
    } finally {
      window.altinelFinishLoading();
    }
  }
  const start = () => prepareImages().catch(() => window.altinelFinishLoading?.());
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
