/* Bounded title parallax and visibility state for the decorative title particles. */
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
    let mobileWidth = 0;
    let mobileImageWidth = 0;
    let mobileImageHeight = 0;
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
      const mobile = window.innerWidth <= 720;
      if (mobile) {
        // Browser toolbar changes must not resize the artwork while scrolling.
        const width = image.clientWidth;
        if (width !== mobileWidth) {
          mobileWidth = width;
          mobileImageHeight = Math.max(image.clientHeight, width * (848 / 1673));
          mobileImageWidth = mobileImageHeight * (1673 / 848);
          image.style.setProperty('--hero-mobile-bg-width', `${mobileImageWidth}px`);
          image.style.setProperty('--hero-mobile-bg-height', `${mobileImageHeight}px`);
          // Keep the existing horizontal speed and starting position.
          const overflow = Math.max(0, mobileImageWidth - width);
          const duration = Math.max(0.001, overflow / (width * .27) * (68.7272727273 / 1.1));
          image.style.setProperty('--hero-mobile-pan-duration', `${duration}s`);
          image.style.setProperty('--hero-mobile-pan-delay', `${-duration * 0.411248981392}s`);
        }
      } else {
        mobileWidth = 0;
      }
      const strength = mobile ? 4.5 : window.innerWidth >= 981 ? 9 : 6;
      limit = Math.min(height * .04, mobile ? 24 : 40) * strength;
      schedule();
    };
    const onScroll = () => { if (visible) schedule(); };
    hero.classList.add('has-parallax', 'is-title-visible');
    measure();
    window.addEventListener('scroll', onScroll, {passive: true});
    window.addEventListener('resize', measure);
    let visibility;
    if ('IntersectionObserver' in window) {
      visibility = new IntersectionObserver(entries => {
        visible = entries[0].isIntersecting;
        hero.classList.toggle('is-title-visible', visible);
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
      hero.classList.remove('has-parallax', 'is-title-visible');
      for (const prop of ['--hero-parallax-y', '--hero-mobile-bg-width', '--hero-mobile-bg-height', '--hero-mobile-pan-duration', '--hero-mobile-pan-delay']) image.style.removeProperty(prop);
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
