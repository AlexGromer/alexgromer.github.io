/* Theme toggle, scroll-spy, reveal on scroll, menu close. No dependencies. */
(function () {
  'use strict';
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function systemDark() {
    return !!(window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
  }
  function currentTheme() {
    var t = root.getAttribute('data-theme');
    return t === 'light' || t === 'dark' ? t : (systemDark() ? 'dark' : 'light');
  }

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.hidden = false;
    var sync = function () {
      var dark = currentTheme() === 'dark';
      toggle.setAttribute('aria-pressed', dark ? 'true' : 'false');
      toggle.setAttribute('aria-label', dark ? 'Dark theme on. Switch to light theme' : 'Light theme on. Switch to dark theme');
    };
    toggle.addEventListener('click', function () {
      var next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) { /* ignore */ }
      sync();
    });
    sync();
  }

  /* close the mobile menu after a choice or on Escape */
  var menu = document.querySelector('details.nav-narrow');
  if (menu) {
    menu.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('a')) menu.removeAttribute('open');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.hasAttribute('open')) {
        menu.removeAttribute('open');
        var s = menu.querySelector('summary');
        if (s) s.focus();
      }
    });
  }

  if (!('IntersectionObserver' in window)) return;

  /* scroll-spy: mark the nav link of the section in the middle of the view */
  var links = document.querySelectorAll('.nav-wide a[href^="#"], .nav-narrow a[href^="#"]');
  var sections = [];
  links.forEach(function (a) {
    var id = a.getAttribute('href').slice(1);
    var s = document.getElementById(id);
    if (s && sections.indexOf(s) < 0) sections.push(s);
  });
  if (sections.length) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var id = en.target.id;
        links.forEach(function (a) {
          if (a.getAttribute('href') === '#' + id) a.setAttribute('aria-current', 'true');
          else a.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach(function (s) { spy.observe(s); });
    var hero = document.getElementById('top');
    if (hero) {
      new IntersectionObserver(function (en) {
        if (en[0].isIntersecting) links.forEach(function (a) { a.removeAttribute('aria-current'); });
      }, { rootMargin: '-40% 0px -55% 0px' }).observe(hero);
    }
  }

  /* reveal: content stays visible unless this script runs and motion is allowed */
  if (!reduce) {
    var items = document.querySelectorAll('.reveal');
    if (items.length) {
      root.classList.add('js-reveal');
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add('is-in'); io.unobserve(en.target); }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
      items.forEach(function (n, i) {
        n.style.setProperty('--i', String(i % 6));
        io.observe(n);
      });
    }
  }
})();
