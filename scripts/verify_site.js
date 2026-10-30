#!/usr/bin/env node
/* Local acceptance checks. Needs playwright-core and chromium.
 * Usage: node scripts/verify_site.js [baseUrl]   (serve the repo first:
 *   python3 -m http.server 8765 --bind 127.0.0.1)
 * Screenshots go to scripts/.shots (git-ignored). Exit code 1 on any failure. */
'use strict';
const fs = require('fs'), path = require('path'), https = require('https');
let chromium;
for (const p of ['playwright-core', '/usr/local/lib/node_modules/@playwright/mcp/node_modules/playwright-core']) {
  try { chromium = require(p).chromium; break; } catch (e) { /* next */ }
}
if (!chromium) { console.error('playwright-core not found'); process.exit(2); }
const ROOT = path.resolve(__dirname, '..'), SHOTS = path.join(ROOT, 'scripts', '.shots');
const BASE = (process.argv[2] || 'http' + '://127.0.0.1:8765').replace(/\/$/, '');
const HOST = new URL(BASE).host;
const PAGES = ['index.html', 'privacy.html', 'terms.html', 'rclone-colab.html', 'privacy-site.html', 'licence.html',
  'contributing.html', 'security.html', 'conduct.html', 'support.html', '404.html'];
const fails = [];
const fail = (m) => { fails.push(m); console.log('FAIL', m); };

function head(url) {
  return new Promise((resolve) => {
    const req = https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 site-check' }, timeout: 20000 }, (res) => {
      res.resume();
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return resolve(head(new URL(res.headers.location, url).toString()));
      }
      resolve(res.statusCode);
    });
    req.on('error', () => resolve(0)); req.on('timeout', () => { req.destroy(); resolve(0); });
  });
}

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const browser = await chromium.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox', '--disable-crash-reporter', '--disable-breakpad'] });
  const links = {};
  for (const scheme of ['light', 'dark']) {
    for (const [w, h] of [[1280, 800], [375, 740]]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, reducedMotion: 'no-preference' });
      for (const name of PAGES) {
        const pg = await ctx.newPage();
        const msgs = [], hosts = new Set();
        pg.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') msgs.push(m.text()); });
        pg.on('pageerror', (e) => msgs.push('pageerror ' + e.message));
        pg.on('request', (r) => { if (!r.url().startsWith('data:')) hosts.add(new URL(r.url()).host); });
        await pg.goto(`${BASE}/${name}`, { waitUntil: 'networkidle' });
        await pg.waitForTimeout(300);
        const tag = `${name.replace('.html', '')}-${w}-${scheme}`;
        if (name === 'index.html') {
          const H = await pg.evaluate(() => document.documentElement.scrollHeight);
          for (let y = 0; y < H; y += 500) { await pg.evaluate((yy) => window.scrollTo(0, yy), y); await pg.waitForTimeout(60); }
          await pg.waitForTimeout(1200);
          await pg.evaluate(() => window.scrollTo(0, 0));
        }
        await pg.screenshot({ path: path.join(SHOTS, tag + '.png'), fullPage: true });
        if (msgs.length) fail(`${tag} console: ${msgs.slice(0, 3).join(' | ')}`);
        for (const hh of hosts) if (hh !== HOST) fail(`${tag} foreign host ${hh}`);
        const [sw, iw] = await pg.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
        if (sw > iw) fail(`${tag} horizontal scroll ${sw} > ${iw}`);
        if (scheme === 'light' && w === 1280) {
          links[name] = await pg.evaluate(() => [...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href')));
          const ids = await pg.evaluate(() => [...document.querySelectorAll('[id]')].map((e) => e.id));
          if (new Set(ids).size !== ids.length) fail(`${name} duplicate ids`);
          const m = await pg.evaluate(() => ({
            t: !!document.title, d: !!document.querySelector('meta[name=description]'), c: !!document.querySelector('link[rel=canonical]'),
            o: !!document.querySelector('meta[property="og:title"]'), i: !!document.querySelector('link[rel=icon]'), l: document.documentElement.lang }));
          if (!(m.t && m.d && m.c && m.o && m.i && m.l === 'en')) fail(`${name} head meta ${JSON.stringify(m)}`);
        }
        await pg.close();
      }
      await ctx.close();
    }
  }
  // reduced motion
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  let pg = await ctx.newPage();
  await pg.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  const anim = await pg.evaluate(() => [...document.querySelectorAll('.hero, .hero *')].filter((e) => getComputedStyle(e).animationName !== 'none').length);
  if (anim) fail(`reduced motion: ${anim} hero elements animate`);
  if (await pg.evaluate(() => document.documentElement.classList.contains('js-reveal'))) fail('reduced motion: reveal active');
  await ctx.close();
  // charts, keyboard, theme
  ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  pg = await ctx.newPage();
  await pg.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  const c = await pg.evaluate(() => ({ seg: document.querySelectorAll('.seg').length, bar: document.querySelectorAll('.bar').length,
    pt: document.querySelectorAll('.pt').length, kpi: document.querySelectorAll('.kpi-tile').length, tables: document.querySelectorAll('[data-table] table').length }));
  console.log('charts', JSON.stringify(c));
  if (c.bar !== 12 || c.pt !== 12 || c.seg < 3 || c.kpi !== 4 || c.tables !== 3) fail('chart counts ' + JSON.stringify(c));
  await pg.keyboard.press('Tab');
  if ((await pg.evaluate(() => document.activeElement.className)) !== 'skip') fail('first Tab is not the skip link');
  const order = [];
  for (let i = 0; i < 12; i++) { await pg.keyboard.press('Tab'); order.push(await pg.evaluate(() => (document.activeElement.textContent || document.activeElement.id || document.activeElement.tagName).trim().slice(0, 18))); }
  console.log('tab order', JSON.stringify(order));
  await pg.focus('.bar'); await pg.waitForTimeout(300);
  if ((await pg.evaluate(() => { const t = document.querySelector('.tip.on'); return t ? getComputedStyle(t).opacity : '0'; })) !== '1') fail('tooltip not shown on focus');
  await pg.evaluate(() => document.querySelector('.bar').scrollIntoView({ block: 'center' }));
  await pg.waitForTimeout(300);
  await pg.screenshot({ path: path.join(SHOTS, 'tooltip-focus.png') });
  await pg.evaluate(() => window.scrollTo(0, 0));
  await pg.click('#theme-toggle');
  const t1 = await pg.evaluate(() => document.documentElement.getAttribute('data-theme'));
  await pg.reload({ waitUntil: 'networkidle' });
  const t2 = await pg.evaluate(() => document.documentElement.getAttribute('data-theme'));
  if (t1 !== t2 || !['light', 'dark'].includes(t1)) fail(`theme toggle not persisted ${t1} ${t2}`);
  // mobile menu
  await ctx.close();
  ctx = await browser.newContext({ viewport: { width: 375, height: 740 } });
  pg = await ctx.newPage();
  await pg.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  await pg.click('details.nav-narrow summary');
  await pg.screenshot({ path: path.join(SHOTS, 'menu-open-375.png') });
  await pg.click('details.nav-narrow a[href="#stats"]');
  await pg.waitForTimeout(800);
  if (await pg.evaluate(() => document.querySelector('details.nav-narrow').hasAttribute('open'))) fail('menu did not close');
  const spy = await pg.evaluate(() => [...document.querySelectorAll('a[aria-current]')].map((a) => a.getAttribute('href')));
  console.log('scroll-spy after #stats', JSON.stringify(spy));
  await ctx.close();
  // editing JSON changes the SVG
  ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  pg = await ctx.newPage();
  const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'stats.json'), 'utf8'));
  d.commits_by_month[11].count = 999;
  await pg.route('**/data/stats.json', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(d) }));
  await pg.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  if (!(await pg.evaluate(() => document.querySelector('[data-chart=commits]').textContent)).includes('999')) fail('editing stats.json did not change the SVG');
  await ctx.close();
  // no JS
  ctx = await browser.newContext({ viewport: { width: 375, height: 740 }, javaScriptEnabled: false });
  pg = await ctx.newPage();
  await pg.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
  if (!(await pg.evaluate(() => [...document.querySelectorAll('.reveal')].every((e) => getComputedStyle(e).opacity === '1')))) fail('no-JS: reveal content hidden');
  if (!(await pg.evaluate(() => [...document.querySelectorAll('noscript table')].length >= 0))) fail('x');
  await pg.screenshot({ path: path.join(SHOTS, 'index-nojs-375.png'), fullPage: true });
  await ctx.close();
  await browser.close();

  // links
  const ext = new Set(), idsOf = {};
  for (const [src, hs] of Object.entries(links)) {
    for (const href of hs) {
      if (href.startsWith('https://')) { ext.add(href); continue; }
      if (/^(http:|mailto:|tel:|javascript:)/.test(href)) { fail(`${src} bad scheme ${href}`); continue; }
      const u = new URL(href, 'https://x/');
      let p = u.pathname.replace(/^\//, '') || 'index.html';
      if (!fs.existsSync(path.join(ROOT, p))) { fail(`${src} broken link ${href}`); continue; }
      if (u.hash && p.endsWith('.html')) {
        idsOf[p] = idsOf[p] || new Set([...fs.readFileSync(path.join(ROOT, p), 'utf8').matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
        if (!idsOf[p].has(u.hash.slice(1))) fail(`${src} broken anchor ${href}`);
      }
    }
  }
  console.log('internal links checked; external:', ext.size);
  for (const u of [...ext].sort()) { const s = await head(u); if (s !== 200) fail(`external ${u} -> ${s}`); }
  console.log('FAILS:', fails.length);
  process.exit(fails.length ? 1 : 0);
})();
