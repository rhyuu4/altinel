/* One-time section reveals and row-based card staggering; native scrolling stays intact. */
(() => {
  'use strict';
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const seenCards = new Set();
  const seenElements = new WeakSet();
  let active = false;
  let observer;
  let gridObserver;
  let focusHandler;
  const cardKey = element => {
    const cast = element.querySelector('[data-kind="cast"][data-id]');
    if (cast) return `cast:${cast.dataset.id}`;
    const boss = element.querySelector('[data-boss-reveal]');
    return boss ? `boss:${boss.dataset.bossReveal}` : null;
  };
  const reveal = element => {
    seenElements.add(element);
    const key = cardKey(element);
    if (key) seenCards.add(key);
    element.classList.add('is-revealed');
    observer?.unobserve(element);
  };
  const start = () => {
    if (active || motion.matches || !('IntersectionObserver' in window)) return;
    active = true;
    const watched = new WeakSet();
    observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) reveal(entry.target);
    }, {threshold: 0.08, rootMargin: '0px 0px -24px 0px'});
    const watch = (element, delay = 0) => {
      if (watched.has(element)) return;
      watched.add(element);
      const key = cardKey(element);
      if (seenElements.has(element) || (key && seenCards.has(key))) return;
      element.style.setProperty('--reveal-delay', `${delay}ms`);
      element.classList.add('scroll-reveal');
      observer.observe(element);
    };
    document.querySelectorAll([
      '#academy > .wrap', '#setting > .wrap',
      '#roster .section-heading', '#roster .roster-toolbar',
      '#targets .section-heading', '#targets .spoiler-notice',
      '#enter .closing-content'
    ].join(',')).forEach(element => watch(element));
    const watchGrid = grid => {
      const columns = getComputedStyle(grid).gridTemplateColumns.split(/\s+/).length;
      [...grid.children].forEach((card, index) => {
        if (card.matches('.roster-card,.boss-card')) watch(card, index % columns * 50);
      });
    };
    const grids = [...document.querySelectorAll('#roster-grid,#boss-grid')];
    grids.forEach(watchGrid);
    gridObserver = new MutationObserver(records => {
      for (const record of records) {
        for (const node of record.removedNodes) if (node.nodeType === 1) observer.unobserve(node);
      }
      grids.forEach(watchGrid);
    });
    grids.forEach(grid => gridObserver.observe(grid, {childList: true}));
    focusHandler = event => {
      let element = event.target.closest('.scroll-reveal');
      while (element) {
        element.style.setProperty('--reveal-delay', '0ms');
        reveal(element);
        element = element.parentElement?.closest('.scroll-reveal');
      }
    };
    document.addEventListener('focusin', focusHandler);
  };
  const stop = () => {
    observer?.disconnect();
    gridObserver?.disconnect();
    if (focusHandler) document.removeEventListener('focusin', focusHandler);
    document.querySelectorAll('.scroll-reveal').forEach(element => {
      seenElements.add(element);
      const key = cardKey(element);
      if (key) seenCards.add(key);
      element.classList.remove('scroll-reveal', 'is-revealed');
      element.style.removeProperty('--reveal-delay');
    });
    active = false;
  };
  const ready = () => {
    if (document.documentElement.classList.contains('is-loading')) {
      window.addEventListener('altinel:ready', start, {once: true});
    } else start();
  };
  motion.addEventListener('change', () => {
    if (motion.matches) stop();
    else ready();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, {once: true});
  else ready();
})();
