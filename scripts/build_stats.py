#!/usr/bin/env python3
"""Build data/stats.json from the public GitHub API (stdlib only).

Usage: python3 scripts/build_stats.py [--refresh] [--offline]

* Repositories come from data/projects.json (allow-list of public repos).
* GITHUB_TOKEN is optional; without it the API allows 60 requests/hour, and
  one run needs about 30. Responses are cached in scripts/.cache (git-ignored)
  for CACHE_TTL seconds; --refresh ignores the cache, --offline uses it only.
* Output is deterministic: sorted keys, no volatile fields except the date
  `generated_at` (UTC day; override with SOURCE_DATE_EPOCH).
* On any API error (rate limit included) nothing is written: the JSON is
  built in memory and replaced atomically at the end.
* The same run refreshes the static no-JS fallback inside index.html between
  the `stats:kpi` and `stats:noscript` markers.
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
    token = os.environ.get("GITHUB_TOKEN")
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
        '        <div class="kpi-tile"><dt>%s</dt><dd data-kpi="%s">%d</dd></div>' % (
            label, label.lower().replace(" ", "_"), val) for label, val in tiles)
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
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stats, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    tmp.replace(out)
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
