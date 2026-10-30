#!/usr/bin/env python3
"""Build data/stats.json from the public GitHub API (stdlib only).

Usage: python3 scripts/build_stats.py [--refresh] [--offline]

* Repositories come from data/projects.json (allow-list of public repos).
* GITHUB_TOKEN (or GH_TOKEN) is optional; without it the API allows 60 requests/hour, and
  one run needs about 30. Responses are cached in scripts/.cache (git-ignored)
  for CACHE_TTL seconds; --refresh ignores the cache, --offline uses it only.
* Output is deterministic: sorted keys, no volatile fields except the date
  `generated_at` (UTC day; override with SOURCE_DATE_EPOCH).
* On any API error (rate limit included) nothing is written: the JSON is
  built in memory and replaced atomically at the end.
* If nothing but the date would change, the previous `generated_at` is kept, so
  a scheduled run produces no commit on days without new data.
* The same run refreshes the static no-JS fallback inside index.html between
  the `stats:kpi` and `stats:noscript` markers, and writes two self-contained
  SVG cards for the profile README: img/stats-overview.svg, img/stats-langs.svg.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / ".cache"
CACHE_TTL = 6 * 3600
API = "https://api.github.com"
TOP_LANGS = 7
MONTHS = 12


class ApiError(RuntimeError):
    pass


def now_utc():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def get(url, refresh=False, offline=False):
    """GET JSON with an on-disk cache. Returns (status, data)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if key.exists() and not refresh:
        if offline or time.time() - key.stat().st_mtime < CACHE_TTL:
            return tuple(json.loads(key.read_text()))
    if offline:
        raise ApiError("offline and no cache for " + url)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "alexgromer-site-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, data = resp.status, json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code == 409:  # empty repository
            status, data = 409, []
        elif err.code in (403, 429):
            raise ApiError("rate limit or forbidden (%d) for %s" % (err.code, url))
        else:
            raise ApiError("HTTP %d for %s" % (err.code, url))
    except (urllib.error.URLError, TimeoutError) as err:
        raise ApiError("network error for %s: %s" % (url, err))
    tmp = key.with_suffix(".tmp")
    tmp.write_text(json.dumps([status, data]))
    tmp.replace(key)
    return status, data


def month_keys(today):
    y, m = today.year, today.month
    keys = []
    for _ in range(MONTHS):
        keys.append("%04d-%02d" % (y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(keys))


def build(refresh, offline):
    projects = json.loads((ROOT / "data" / "projects.json").read_text())
    login = projects["login"]
    allowed = [r["name"] for r in projects["repos"]]
    today = now_utc()
    months = month_keys(today)
    since = months[0] + "-01T00:00:00Z"

    _, listing = get("%s/users/%s/repos?per_page=100&type=owner" % (API, login), refresh, offline)
    by_name = {r["name"]: r for r in listing}
    missing = [n for n in allowed if n not in by_name]
    if missing:
        raise ApiError("repositories not found: " + ", ".join(missing))

    lang_bytes = {}
    commits = {k: 0 for k in months}
    repos = []
    for name in sorted(allowed):
        r = by_name[name]
        langs = {}
        if not r["fork"]:
            _, langs = get("%s/repos/%s/%s/languages" % (API, login, name), refresh, offline)
            for lang, n in langs.items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + int(n)
            page = 1
            while True:
                url = "%s/repos/%s/%s/commits?author=%s&since=%s&per_page=100&page=%d" % (
                    API, login, name, login, since, page)
                _, items = get(url, refresh, offline)
                for c in items:
                    key = c["commit"]["author"]["date"][:7]
                    if key in commits:
                        commits[key] += 1
                if len(items) < 100:
                    break
                page += 1
        top = sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))
        repos.append({
            "created": r["created_at"][:10],
            "language": top[0][0] if top else (r.get("language") or ""),
            "name": name,
            "pushed": r["pushed_at"][:10],
            "stars": int(r["stargazers_count"]),
        })
    repos.sort(key=lambda x: (x["created"], x["name"]))

    total = sum(lang_bytes.values()) or 1
    ranked = sorted(lang_bytes.items(), key=lambda kv: (-kv[1], kv[0]))
    langs_out = [{"bytes": b, "name": n, "percent": round(100.0 * b / total, 1)}
                 for n, b in ranked[:TOP_LANGS]]
    rest = sum(b for _, b in ranked[TOP_LANGS:])
    if rest:
        langs_out.append({"bytes": rest, "name": "Other", "percent": round(100.0 * rest / total, 1)})

    return {
        "commits_by_month": [{"count": commits[k], "month": k} for k in months],
        "generated_at": today.strftime("%Y-%m-%d"),
        "kpi": {
            "languages": len(ranked),
            "merged_prs": len(projects["merged_prs"]),
            "repos": len(repos),
            "stars": sum(r["stars"] for r in repos),
        },
        "languages": langs_out,
        "login": login,
        "repos": repos,
    }


def kib(n):
    return "%.1f" % (n / 1024.0)


def render_static(stats):
    kpi = stats["kpi"]
    tiles = [("Repositories", kpi["repos"]), ("Stars", kpi["stars"]),
             ("Merged PRs", kpi["merged_prs"]), ("Languages", kpi["languages"])]
    kpi_html = "\n".join(
        '        <div class="kpi-tile"><dt%s>%s</dt><dd data-kpi="%s">%d</dd></div>' % (
            ' data-kpi-label="languages"' if label == "Languages" else "",
            "Languages (%d shown)" % len(stats["languages"]) if label == "Languages" else label,
            label.lower().replace(" ", "_"), val) for label, val in tiles)
    rows_l = "".join("<tr><td>%s</td><td>%s%%</td><td>%s KiB</td></tr>" % (
        l["name"], l["percent"], kib(l["bytes"])) for l in stats["languages"])
    rows_c = "".join("<tr><td>%s</td><td>%d</td></tr>" % (c["month"], c["count"])
                     for c in stats["commits_by_month"])
    rows_r = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td></tr>" % (
        r["created"], r["name"], r["language"] or "n/a", r["stars"]) for r in stats["repos"])
    noscript = (
        "      <noscript>\n"
        '        <div class="tables">\n'
        "          <table><caption>Languages by bytes (generated %s)</caption>"
        "<thead><tr><th>Language</th><th>Share</th><th>Size</th></tr></thead><tbody>%s</tbody></table>\n"
        "          <table><caption>Commits per month</caption>"
        "<thead><tr><th>Month</th><th>Commits</th></tr></thead><tbody>%s</tbody></table>\n"
        "          <table><caption>Repositories by creation date</caption>"
        "<thead><tr><th>Created</th><th>Repository</th><th>Language</th><th>Stars</th></tr></thead><tbody>%s</tbody></table>\n"
        "        </div>\n"
        "      </noscript>") % (stats["generated_at"], rows_l, rows_c, rows_r)
    return kpi_html, noscript


# ---- SVG cards (profile README) -------------------------------------------
# Fixed dark card with its own background: readable on a light and a dark page,
# and independent of prefers-color-scheme (GitHub proxies the file as an image).
CARD = {"bg": "#0f1b2d", "tile": "#14253b", "line": "#28425f", "text": "#d9e2ec",
        "muted": "#9fb3c8", "accent": "#5fb3ff"}
LANG_COLOURS = ["#5fb3ff", "#f2a65a", "#7bd88f", "#c792ea", "#ff7b86", "#f0d264", "#4dd0c4", "#9fb3c8"]
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
CARD_W = 800


def card_open(height, title, desc):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'role="img" aria-labelledby="t d">\n'
        '  <title id="t">%s</title>\n  <desc id="d">%s</desc>\n'
        '  <rect x="0.5" y="0.5" width="%d" height="%d" rx="14" fill="%s" stroke="%s"/>\n'
        '  <g font-family="%s">\n' % (
            CARD_W, height, CARD_W, height, escape(title), escape(desc),
            CARD_W - 1, height - 1, CARD["bg"], CARD["line"], FONT))


def card_head(title, note):
    return (
        '    <text x="24" y="32" font-size="15" font-weight="700" fill="%s">%s</text>\n'
        '    <text x="%d" y="32" font-size="12" text-anchor="end" fill="%s">%s</text>\n' % (
            CARD["text"], escape(title), CARD_W - 24, CARD["muted"], escape(note)))


def render_overview(stats):
    kpi = stats["kpi"]
    commits = sum(c["count"] for c in stats["commits_by_month"])
    tiles = [(kpi["repos"], "public repositories"), (kpi["stars"], "stars"),
             (commits, "commits, last 12 months"), (kpi["languages"], "languages")]
    gap, tw = 12, (CARD_W - 48 - 3 * 12) / 4.0
    desc = "; ".join("%s %s" % (format(v, ","), lbl) for v, lbl in tiles)
    out = [card_open(146, "GitHub overview for " + stats["login"], desc),
           card_head(stats["login"] + " on GitHub", "as of " + stats["generated_at"])]
    for i, (val, lbl) in enumerate(tiles):
        x = 24 + i * (tw + gap)
        out.append('    <rect x="%.1f" y="48" width="%.1f" height="82" rx="10" fill="%s" stroke="%s"/>\n' % (
            x, tw, CARD["tile"], CARD["line"]))
        out.append('    <text x="%.1f" y="88" font-size="30" font-weight="700" fill="%s">%s</text>\n' % (
            x + 16, CARD["accent"], format(val, ",")))
        out.append('    <text x="%.1f" y="114" font-size="12" fill="%s">%s</text>\n' % (x + 16, CARD["muted"], escape(lbl)))
    out.append("  </g>\n</svg>\n")
    return "".join(out)


def seg_widths(values, avail, minimum):
    """Widths summing to `avail`; shares below `minimum` px get `minimum`, the rest are scaled down."""
    n = len(values)
    if avail < minimum * n:
        return [avail / float(n)] * n
    fixed = [False] * n
    out = [0.0] * n
    for _ in range(n):
        room = avail - minimum * sum(fixed)
        free = sum(v for v, f in zip(values, fixed) if not f)
        for i, v in enumerate(values):
            out[i] = minimum if fixed[i] else (room * v / free if free else room / float(n - sum(fixed)))
        newly = [i for i in range(n) if not fixed[i] and out[i] < minimum]
        for i in newly:
            fixed[i] = True
            out[i] = minimum
        if not newly:
            break
    return out


def render_langs(stats):
    langs = stats["languages"]
    n = len(langs)
    cols, colw = 4, (CARD_W - 48) / 4.0
    rows = (n + cols - 1) // cols
    height = 84 + rows * 26 + 14
    gap = 2
    widths = seg_widths([l["bytes"] for l in langs], CARD_W - 48 - gap * (n - 1), 3.0)
    colour = lambda i, l: LANG_COLOURS[7] if l["name"] == "Other" else LANG_COLOURS[min(i, 6)]
    desc = ", ".join("%s %s%%" % (l["name"], l["percent"]) for l in langs)
    out = [card_open(height, "Languages by bytes for " + stats["login"], desc),
           card_head("Languages by bytes", "public non-fork repositories, as of " + stats["generated_at"])]
    x = 24.0
    for i, l in enumerate(langs):
        out.append('    <rect x="%.1f" y="48" width="%.1f" height="16" rx="3" fill="%s"/>\n' % (x, widths[i], colour(i, l)))
        x += widths[i] + gap
    for i, l in enumerate(langs):
        cx, cy = 24 + (i % cols) * colw, 92 + (i // cols) * 26
        out.append('    <rect x="%.1f" y="%d" width="10" height="10" rx="2" fill="%s"/>\n' % (cx, cy, colour(i, l)))
        out.append('    <text x="%.1f" y="%d" font-size="13" fill="%s">%s</text>\n' % (cx + 18, cy + 10, CARD["text"], escape(l["name"])))
        out.append('    <text x="%.1f" y="%d" font-size="13" text-anchor="end" fill="%s">%s%%</text>\n' % (
            cx + colw - 16, cy + 10, CARD["muted"], l["percent"]))
    out.append("  </g>\n</svg>\n")
    return "".join(out)


def write_atomic(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def patch(text, name, body):
    pat = re.compile(r"(<!-- %s:start -->\n)(.*?)(\n\s*<!-- %s:end -->)" % (name, name), re.S)
    if not pat.search(text):
        raise ApiError("marker %s not found in index.html" % name)
    return pat.sub(lambda m: m.group(1) + body + m.group(3), text)


def main(argv):
    refresh = "--refresh" in argv
    offline = "--offline" in argv
    try:
        stats = build(refresh, offline)
    except ApiError as err:
        print("build_stats: " + str(err), file=sys.stderr)
        return 1
    out = ROOT / "data" / "stats.json"
    if out.exists():
        try:
            old = json.loads(out.read_text())
        except ValueError:
            old = {}
        if {k: v for k, v in old.items() if k != "generated_at"} == \
                {k: v for k, v in stats.items() if k != "generated_at"} and "generated_at" in old:
            stats["generated_at"] = old["generated_at"]
    write_atomic(out, json.dumps(stats, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    (ROOT / "img").mkdir(exist_ok=True)
    write_atomic(ROOT / "img" / "stats-overview.svg", render_overview(stats))
    write_atomic(ROOT / "img" / "stats-langs.svg", render_langs(stats))
    index = ROOT / "index.html"
    if index.exists():
        kpi_html, noscript = render_static(stats)
        text = index.read_text()
        try:
            text = patch(text, "stats:kpi", kpi_html)
            text = patch(text, "stats:noscript", noscript)
        except ApiError as err:
            print("build_stats: warning: " + str(err), file=sys.stderr)
        else:
            index.write_text(text)
    print("wrote %s (%d repos, %d languages)" % (out.relative_to(ROOT), len(stats["repos"]), stats["kpi"]["languages"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
