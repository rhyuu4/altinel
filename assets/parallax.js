/* A small, bounded background offset; never changes native scroll behavior or title text. */
(() => {
  'use strict';
  const hero = document.querySelector('.hero-landscape');
  const image = hero?.querySelector('.hero-image');
  if (!image) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let cleanup = () => {};
  const start = () => {
    cleanup();
    if (motion.matches) return;
    let frame = 0;
    let visible = true;
    let top = 0;
    let height = 1;
    let limit = 0;
    const paint = () => {
      frame = 0;
      const progress = Math.min(1, Math.max(0, (window.scrollY - top) / height));
      image.style.setProperty('--hero-parallax-y', `${(progress * limit).toFixed(2)}px`);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(paint); };
    const measure = () => {
      const rect = hero.getBoundingClientRect();
      top = rect.top + window.scrollY;
      height = Math.max(1, rect.height);
      limit = Math.min(height * .04, window.innerWidth <= 720 ? 24 : 40);
      schedule();
    };
    const onScroll = () => { if (visible) schedule(); };
    hero.classList.add('has-parallax');
    measure();
    window.addEventListener('scroll', onScroll, {passive: true});
    window.addEventListener('resize', measure);
    let visibility;
    if ('IntersectionObserver' in window) {
      visibility = new IntersectionObserver(entries => {
        visible = entries[0].isIntersecting;
        schedule();
      });
      visibility.observe(hero);
    }
    let resize;
    if ('ResizeObserver' in window) {
      resize = new ResizeObserver(measure);
      resize.observe(hero);
      const header = document.querySelector('.site-header');
      if (header) resize.observe(header);
    }
    cleanup = () => {
      cancelAnimationFrame(frame);
      visibility?.disconnect();
      resize?.disconnect();
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', measure);
      hero.classList.remove('has-parallax');
      image.style.removeProperty('--hero-parallax-y');
    };
  };
  const ready = () => {
    if (document.documentElement.classList.contains('is-loading')) window.addEventListener('altinel:ready', start, {once: true});
    else start();
  };
  motion.addEventListener('change', () => { if (motion.matches) cleanup(); else ready(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready, {once: true});
  else ready();
})();
