/* Draws the three charts, the KPI tiles and the data tables from data/stats.json. */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var uid = 0;

  function svgEl(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmt(n) { return Number(n).toLocaleString('en-US'); }
  function kib(b) { return (b / 1024).toFixed(1); }
  function clip(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  function load(url) {
    return fetch(url, { credentials: 'omit' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' ' + r.status);
      return r.json();
    });
  }

  function validate(d, allowed) {
    var ok = d && Array.isArray(d.commits_by_month) && d.commits_by_month.length === 12 &&
      Array.isArray(d.languages) && Array.isArray(d.repos) && d.kpi;
    if (!ok) return false;
    var nonneg = function (n) { return typeof n === 'number' && isFinite(n) && n >= 0; };
    if (!d.commits_by_month.every(function (c) { return /^\d{4}-\d{2}$/.test(c.month) && nonneg(c.count); })) return false;
    if (!d.languages.every(function (l) { return typeof l.name === 'string' && nonneg(l.bytes) && nonneg(l.percent); })) return false;
    if (!d.repos.every(function (r) {
      return /^\d{4}-\d{2}-\d{2}$/.test(r.created) && nonneg(r.stars) && typeof r.name === 'string' &&
        (!allowed || allowed.indexOf(r.name) >= 0);
    })) return false;
    return ['repos', 'stars', 'merged_prs', 'languages'].every(function (k) { return nonneg(d.kpi[k]); });
  }

  /* colour index per language = rank by bytes (stable for the same data), Other = 7 */
  function langIndex(d) {
    var map = {};
    d.languages.forEach(function (l, i) { map[l.name] = l.name === 'Other' ? 7 : Math.min(i, 6); });
    return map;
  }

  function Tip(body) {
    var tip = h('div', 'tip');
    tip.setAttribute('aria-hidden', 'true');
    body.appendChild(tip);
    return {
      show: function (target, text) {
        tip.textContent = text;
        var b = body.getBoundingClientRect(), t = target.getBoundingClientRect();
        tip.classList.add('on');
        var w = tip.offsetWidth;
        var x = t.left - b.left + t.width / 2 - w / 2;
        x = Math.max(0, Math.min(x, b.width - w));
        tip.style.left = x + 'px';
        tip.style.top = Math.max(0, t.top - b.top - tip.offsetHeight - 8) + 'px';
      },
      hide: function () { tip.classList.remove('on'); }
    };
  }
  function bindTip(node, tip, text) {
    node.setAttribute('role', 'img');
    node.setAttribute('aria-label', text);
    node.addEventListener('pointerenter', function () { tip.show(node, text); });
    node.addEventListener('pointerleave', function () { tip.hide(); });
    node.addEventListener('focus', function () { tip.show(node, text); });
    node.addEventListener('blur', function () { tip.hide(); });
    node.addEventListener('keydown', function (e) { if (e.key === 'Escape') tip.hide(); });
  }
  /* Roving tabindex: one Tab stop per chart; arrow keys, Home and End move between its points. */
  function rove(nodes) {
    nodes.forEach(function (n, i) {
      n.setAttribute('tabindex', i === 0 ? '0' : '-1');
      n.addEventListener('focus', function () {
        nodes.forEach(function (m) { m.setAttribute('tabindex', m === n ? '0' : '-1'); });
      });
      n.addEventListener('keydown', function (e) {
        var to = -1, last = nodes.length - 1;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') to = Math.min(i + 1, last);
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') to = Math.max(i - 1, 0);
        else if (e.key === 'Home') to = 0;
        else if (e.key === 'End') to = last;
        if (to < 0) return;
        e.preventDefault();
        nodes[to].focus();
      });
    });
  }
  function frame(body, w, hgt, title, desc) {
    var id = 'c' + (++uid);
    var s = svgEl('svg', { viewBox: '0 0 ' + w + ' ' + hgt, width: w, height: hgt, role: 'group', 'aria-labelledby': id + 't ' + id + 'd' });
    svgEl('title', { id: id + 't' }, s).textContent = title;
    svgEl('desc', { id: id + 'd' }, s).textContent = desc;
    return s;
  }

  /* Segment widths that sum to exactly `avail`: tiny shares get MIN px, the others are scaled down. */
  function segWidths(bytes, avail, min) {
    var total = bytes.reduce(function (a, b) { return a + b; }, 0) || 1;
    var fixed = bytes.map(function () { return false; });
    var out = bytes.map(function (b) { return avail * b / total; });
    if (avail < min * bytes.length) return bytes.map(function () { return avail / bytes.length; });
    for (var pass = 0; pass < bytes.length; pass++) {
      var nFixed = fixed.filter(Boolean).length, freeBytes = 0, changed = false;
      bytes.forEach(function (b, i) { if (!fixed[i]) freeBytes += b; });
      var room = avail - nFixed * min;
      bytes.forEach(function (b, i) {
        if (fixed[i]) { out[i] = min; return; }
        out[i] = freeBytes ? room * b / freeBytes : room / (bytes.length - nFixed);
      });
      out.forEach(function (x, i) { if (!fixed[i] && x < min) { fixed[i] = true; out[i] = min; changed = true; } });
      if (!changed) break;
    }
    return out;
  }

  function drawLangs(body, d, w) {
    var gap = 3, hgt = 44, n = d.languages.length;
    var avail = w - gap * (n - 1);
    var idx = langIndex(d);
    var widths = segWidths(d.languages.map(function (l) { return l.bytes; }), avail, 4);
    var s = frame(body, w, hgt, 'Languages by bytes',
      d.languages.map(function (l) { return l.name + ' ' + l.percent + '%'; }).join(', '));
    var tip = Tip(body), x = 0, nodes = [];
    d.languages.forEach(function (l, i) {
      var sw = widths[i];
      var r = svgEl('rect', { x: x.toFixed(1), y: 0, width: sw.toFixed(1), height: hgt, rx: 6, 'class': 'seg sw-' + idx[l.name] }, s);
      r.style.setProperty('--i', String(i));
      bindTip(r, tip, l.name + ': ' + l.percent + '% (' + kib(l.bytes) + ' KiB)');
      nodes.push(r);
      x += sw + gap;
    });
    rove(nodes);
    body.insertBefore(s, body.firstChild);
  }

  function drawCommits(body, d, w) {
    var padL = 34, padT = 24, padB = 42, hgt = 230;
    var data = d.commits_by_month, max = 0;
    data.forEach(function (c) { if (c.count > max) max = c.count; });
    var step = max <= 10 ? 5 : max <= 50 ? 10 : max <= 100 ? 25 : max <= 200 ? 50 : 100;
    var top = Math.max(step, Math.ceil(max / step) * step);
    var ph = hgt - padT - padB, slot = (w - padL) / data.length, bw = Math.max(8, slot * 0.6);
    var total = data.reduce(function (a, c) { return a + c.count; }, 0);
    var s = frame(body, w, hgt, 'Commits per month, last 12 months',
      total + ' commits in 12 months; peak ' + max + ' in ' + data.filter(function (c) { return c.count === max; })[0].month);
    var tip = Tip(body), nodes = [];
    [0, 0.5, 1].forEach(function (f) {
      var y = padT + ph - ph * f;
      svgEl('line', { x1: padL, x2: w, y1: y, y2: y, 'class': 'grid' }, s);
      svgEl('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end', 'class': 'axis-label' }, s).textContent = String(Math.round(top * f));
    });
    var mon = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    data.forEach(function (c, i) {
      var bh = Math.max(ph * c.count / top, 1), x = padL + slot * i + (slot - bw) / 2, y = padT + ph - bh;  /* 1px baseline for zero months, so the point can show focus */
      var m = parseInt(c.month.slice(5), 10);
      var r = svgEl('rect', { x: x.toFixed(1), y: y.toFixed(1), width: bw.toFixed(1), height: bh.toFixed(1), rx: 4, 'class': 'bar' }, s);
      r.style.setProperty('--i', String(i));
      bindTip(r, tip, c.month + ': ' + c.count + (c.count === 1 ? ' commit' : ' commits'));
      nodes.push(r);
      var cx = x + bw / 2;
      if (c.count > 0 && slot >= 26) svgEl('text', { x: cx, y: y - 5, 'text-anchor': 'middle', 'class': 'val' }, s).textContent = String(c.count);
      svgEl('text', { x: cx, y: hgt - padB + 16, 'text-anchor': 'middle' }, s).textContent = mon[m - 1];
      if (i === 0 || m === 1) svgEl('text', { x: cx, y: hgt - padB + 30, 'text-anchor': 'middle', 'class': 'axis-label' }, s).textContent = c.month.slice(0, 4);
    });
    rove(nodes);
    body.insertBefore(s, body.firstChild);
  }

  function drawTimeline(body, d, w, pitches) {
    var repos = d.repos, idx = langIndex(d);
    if (w < 720) {
      var ol = h('ol', 'tl-list');
      repos.forEach(function (r) {
        var li = h('li');
        li.appendChild(h('span', 'd', r.created));
        var a = h('a', null, r.name);
        a.href = 'https://github.com/' + d.login + '/' + r.name;
        a.rel = 'noopener';
        li.appendChild(a);
        li.appendChild(document.createTextNode(' · ' + (r.language || 'n/a') + ' · ★ ' + r.stars));
        ol.appendChild(li);
      });
      body.insertBefore(ol, body.firstChild);
      return;
    }
    var hgt = 230, axisY = 190, padL = 30, padR = 110, n = repos.length;
    var s = frame(body, w, hgt, 'Repositories by creation date',
      n + ' repositories from ' + repos[0].created + ' to ' + repos[n - 1].created + '; dot size grows with stars');
    var tip = Tip(body), nodes = [];
    svgEl('line', { x1: padL - 10, x2: w - padR + 40, y1: axisY, y2: axisY, 'class': 'axis-line' }, s);
    var sp = (w - padL - padR) / Math.max(1, n - 1);
    repos.forEach(function (r, i) {
      var x = padL + sp * i, rad = 6 + 3 * Math.sqrt(r.stars);
      if (i > 0) {
        var gapDays = (Date.parse(r.created) - Date.parse(repos[i - 1].created)) / 864e5;
        if (gapDays > 365) svgEl('text', { x: x - sp / 2, y: axisY + 4, 'text-anchor': 'middle', 'aria-hidden': 'true' }, s).textContent = '//';
      }
      var c = svgEl('circle', { cx: x.toFixed(1), cy: axisY, r: rad.toFixed(1), 'class': 'pt' }, s);
      var info = r.name + ', created ' + r.created + ', ' + (r.language || 'no detected language') + ', ' + r.stars + (r.stars === 1 ? ' star' : ' stars');
      bindTip(c, tip, pitches[r.name] ? info + '. ' + pitches[r.name] : info);
      nodes.push(c);
      var t = svgEl('text', { x: x + 4, y: axisY - rad - 8, transform: 'rotate(-45 ' + (x + 4) + ' ' + (axisY - rad - 8) + ')', 'text-anchor': 'start' }, s);
      t.textContent = clip(r.name, 24);
      svgEl('text', { x: x, y: axisY + 28, 'text-anchor': 'middle', 'class': 'axis-label' }, s).textContent = r.created.slice(0, 7);
    });
    rove(nodes);
    body.insertBefore(s, body.firstChild);
  }

  /* Same-origin inline icons: symbols live in the sprite at the top of index.html. */
  var ICONS = { Go: 'go', Rust: 'rust', C: 'c', Shell: 'bash', Python: 'python', TypeScript: 'ts' };
  function icon(name) {
    var id = ICONS[name], hasSym = id && document.getElementById('i-' + id);
    var s = svgEl('svg', { 'class': 'lang-ico', 'aria-hidden': 'true', viewBox: '0 0 24 24' });
    if (hasSym) svgEl('use', { href: '#i-' + id }, s);
    return s;
  }
  function fillLegend(ul, d) {
    var idx = langIndex(d);
    ul.textContent = '';
    d.languages.forEach(function (l) {
      var li = h('li');
      li.appendChild(h('span', 'swatch sw-' + idx[l.name]));
      li.appendChild(icon(l.name));
      li.appendChild(h('span', null, l.name));
      li.appendChild(h('span', 'num', l.percent + '% · ' + kib(l.bytes) + ' KiB'));
      ul.appendChild(li);
    });
  }
  function table(host, head, rows) {
    host.textContent = '';
    var t = h('table'), thead = h('thead'), tr = h('tr');
    head.forEach(function (x) { tr.appendChild(h('th', null, x)); });
    thead.appendChild(tr); t.appendChild(thead);
    var tb = h('tbody');
    rows.forEach(function (r) {
      var row = h('tr');
      r.forEach(function (c) { row.appendChild(h('td', null, String(c))); });
      tb.appendChild(row);
    });
    t.appendChild(tb); host.appendChild(t);
  }
  function fillTables(d) {
    var q = function (n) { return document.querySelector('[data-table="' + n + '"]'); };
    if (q('lang')) table(q('lang'), ['Language', 'Share', 'Size'], d.languages.map(function (l) { return [l.name, l.percent + '%', kib(l.bytes) + ' KiB']; }));
    if (q('commits')) table(q('commits'), ['Month', 'Commits'], d.commits_by_month.map(function (c) { return [c.month, c.count]; }));
    if (q('repos')) table(q('repos'), ['Created', 'Repository', 'Language', 'Stars'], d.repos.map(function (r) { return [r.created, r.name, r.language || 'n/a', r.stars]; }));
  }
  function fillKpi(d) {
    document.querySelectorAll('[data-kpi]').forEach(function (n) {
      var v = d.kpi[n.getAttribute('data-kpi')];
      if (typeof v === 'number') n.textContent = fmt(v);
    });
    var lab = document.querySelector('[data-kpi-label="languages"]');
    if (lab) lab.textContent = 'Languages (' + d.languages.length + ' shown)';
  }
  function fillRepoBits(d) {
    var idx = langIndex(d);
    d.repos.forEach(function (r) {
      document.querySelectorAll('[data-repo-stars="' + r.name + '"]').forEach(function (n) { n.textContent = '★ ' + r.stars; });
      document.querySelectorAll('[data-repo-lang="' + r.name + '"]').forEach(function (n) {
        var dot = n.querySelector('.dot'), label = n.querySelector('.lbl');
        if (label) label.textContent = r.language || 'n/a';
        if (dot) dot.className = 'dot c' + (r.language && idx[r.language] != null ? idx[r.language] : 7);
      });
    });
  }

  function mount(d, pitches) {
    var charts = [
      { sel: '[data-chart="lang"]', draw: drawLangs },
      { sel: '[data-chart="commits"]', draw: drawCommits },
      { sel: '[data-chart="timeline"]', draw: function (b, dd, w) { drawTimeline(b, dd, w, pitches); } }
    ];
    var io = 'IntersectionObserver' in window && !reduce ? new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target); } });
    }, { threshold: 0.25 }) : null;
    charts.forEach(function (c) {
      var body = document.querySelector(c.sel);
      if (!body) return;
      var lastW = 0, pending = false;
      var render = function () {
        pending = false;
        var w = Math.floor(body.clientWidth);
        if (w < 200 || w === lastW) return;
        lastW = w;
        body.textContent = '';
        c.draw(body, d, w);
      };
      render();
      if (io) io.observe(body); else body.classList.add('in-view');
      if ('ResizeObserver' in window) {
        new ResizeObserver(function () {
          if (!pending) { pending = true; requestAnimationFrame(render); }
        }).observe(body);
      }
    });
    var legend = document.querySelector('[data-legend="lang"]');
    if (legend) fillLegend(legend, d);
    fillTables(d);
    fillKpi(d);
    fillRepoBits(d);
    var meta = document.getElementById('stats-meta');
    if (meta) meta.textContent = 'Generated ' + d.generated_at + ' from the public GitHub API.';
  }

  /* Charts, tables and the legend change the height of #stats after the browser has already
     jumped to a #hash below it. Put the target back once rendering is done, unless the reader
     has started scrolling by themselves. */
  var userMoved = false;
  ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(function (t) {
    window.addEventListener(t, function () { userMoved = true; }, { passive: true, once: true });
  });
  function realign() {
    if (userMoved || !location.hash) return;
    var id = location.hash.slice(1), el, st = document.getElementById('stats');
    try { id = decodeURIComponent(id); } catch (e) { /* keep the raw id */ }
    el = document.getElementById(id);
    if (!el || !st || el === st || !(st.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) return;
    if (st.contains(el)) return;
    el.scrollIntoView({ behavior: 'instant', block: 'start' });
  }
  function settle() {
    realign();
    requestAnimationFrame(realign);
    if (document.readyState !== 'complete') window.addEventListener('load', realign, { once: true });
  }

  var status = document.getElementById('stats-status');
  Promise.all([load('data/stats.json'), load('data/projects.json').catch(function () { return null; })])
    .then(function (res) {
      var stats = res[0], proj = res[1];
      var allowed = proj ? proj.repos.map(function (r) { return r.name; }) : null;
      var pitches = {};
      if (proj) proj.repos.forEach(function (r) { pitches[r.name] = r.pitch; });
      if (!validate(stats, allowed)) throw new Error('stats.json failed validation');
      mount(stats, pitches);
      settle();
    })
    .catch(function () {
      if (status) { status.hidden = false; status.textContent = 'Statistics could not be loaded. The numbers are on the GitHub profile.'; }
      settle();
    });
})();
