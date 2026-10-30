# alexgromer.github.io

Personal site of Alex Gromer, served by GitHub Pages from `main` with no build step: plain HTML, CSS and JavaScript.
No frameworks, no CDN scripts, no analytics, no cookies.

## Layout

| Path | What |
|---|---|
| `index.html` | the home page: hero, about, principles, stats, projects, open source, lab, policies, contact |
| `privacy.html`, `terms.html`, `rclone-colab.html` | the rclone-colab application pages (URLs are referenced by the OAuth consent screen; keep them) |
| `privacy-site.html`, `licence.html`, `contributing.html`, `security.html`, `conduct.html`, `support.html` | site and repository policies |
| `css/site.css` | styles (`style.css` is a copy kept for old links) |
| `js/` | `theme.js` (pre-paint theme), `site.js` (toggle, scroll-spy, reveal), `stats.js` (SVG charts) |
| `data/stats.json`, `data/projects.json` | chart data (generated) and project pitches |
| `scripts/build_stats.py` | builds `data/stats.json` from the public GitHub API |
| `scripts/gen_pages.py` | generates the policy pages and the shared header and footer |

## Refresh the statistics

```sh
python3 scripts/build_stats.py            # uses scripts/.cache for 6 hours
python3 scripts/build_stats.py --refresh  # ignore the cache
```

Standard library only. `GITHUB_TOKEN` is optional (60 requests per hour without it; a run needs about 30).
If the API fails, nothing is written. The script also refreshes the no-JavaScript tables inside `index.html`.
Commit the result.

## Edit the policy pages

Edit the page bodies in `scripts/gen_pages.py`, run `python3 scripts/gen_pages.py`, commit the generated `.html` files.

## Preview

```sh
python3 -m http.server 8000
```

## Licence

MIT, see `LICENSE`.
