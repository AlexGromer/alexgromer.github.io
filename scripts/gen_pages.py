#!/usr/bin/env python3
"""Generate the policy pages and refresh the shared header/footer of index.html.

Static output only (stdlib): run `python3 scripts/gen_pages.py` after editing the
bodies below, then commit the generated .html files. index.html is hand-written;
this script only replaces the regions between its gen:header / gen:footer markers.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://alexgromer.github.io"
UPDATED = ("2026-10-30", "30 October 2026")
CSP = "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
NAV = [("about", "About"), ("principles", "Principles"), ("stats", "Stats"), ("projects", "Projects"),
       ("oss", "Open source"), ("lab", "Lab"), ("policies", "Policies"), ("contact", "Contact")]
MOON = '<svg class="i-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.500A8 8 0 0 1 9.500 4 8 8 0 1 0 20 14.500z"/></svg>'
SUN = '<svg class="i-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.900 4.900l1.400 1.400M17.700 17.700l1.400 1.400M2 12h2M20 12h2M4.900 19.100l1.400-1.400M17.700 6.300l1.400-1.400"/></svg>'
BURGER = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'


def header(prefix, anchors_local):
    base = "" if anchors_local else prefix + "index.html"
    links = "\n".join('        <a href="%s#%s">%s</a>' % (base, i, t) for i, t in NAV)
    links2 = links.replace("        ", "          ")
    home = (prefix + "index.html") if prefix or not anchors_local else "#top"
    return f'''<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{home}"><img src="{prefix}img/favicon.svg" alt="" width="32" height="32"><span>Alex Gromer</span></a>
    <nav class="nav-wide" aria-label="Sections">
{links}
    </nav>
    <details class="nav-narrow">
      <summary>{BURGER}<span>Menu</span></summary>
      <nav class="menu" aria-label="Sections, menu">
{links2}
      </nav>
    </details>
    <button id="theme-toggle" class="theme-toggle" type="button" hidden aria-pressed="false" aria-label="Switch colour theme">{MOON}{SUN}</button>
  </div>
</header>'''


def footer(prefix):
    links = [("security.html", "Security"), ("contributing.html", "Contributing"), ("conduct.html", "Conduct"),
             ("support.html", "Support"), ("licence.html", "Licence"), ("privacy-site.html", "Site privacy"),
             ("rclone-colab.html", "rclone-colab"), ("privacy.html", "rclone-colab privacy"), ("terms.html", "rclone-colab terms")]
    li = "\n".join('      <li><a href="%s%s">%s</a></li>' % (prefix, h, t) for h, t in links)
    return f'''<footer class="site-footer">
  <div class="wrap">
    <ul class="links">
{li}
    </ul>
    <p>&copy; 2026 Alex Gromer. Site source under the <a href="{prefix}licence.html">MIT licence</a>. <a href="https://github.com/AlexGromer/alexgromer.github.io" rel="noopener">Source on GitHub</a>.</p>
    <p class="note">No analytics. No cookies. Static files.</p>
  </div>
</footer>'''


def head(title, desc, path, prefix="", noindex=False):
    robots = '\n<meta name="robots" content="noindex">' if noindex else ""
    return f'''<!doctype html>
<html lang="en">
<head>
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE}/{path}">{robots}
<meta property="og:type" content="article">
<meta property="og:site_name" content="Alex Gromer">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE}/{path}">
<meta property="og:image" content="{SITE}/img/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Alex Gromer: circuit traces and a gear on a dark blue background">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f4f7fa" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0f1b2d" media="(prefers-color-scheme: dark)">
<link rel="icon" href="{prefix}img/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}css/site.css">
<script src="{prefix}js/theme.js"></script>
<script src="{prefix}js/site.js" defer></script>
</head>'''


def page(path, title, desc, h1, body, lede=None, prefix="", noindex=False, updated=True, doc_class="doc"):
    up = ('<p class="updated">Last updated <time datetime="%s">%s</time></p>\n' % UPDATED) if updated else ""
    back = '<a class="back" href="%sindex.html#policies">&larr; All policies</a>\n' % prefix
    out = f'''{head(title, desc, path, prefix, noindex)}
<body>
<a class="skip" href="#main">Skip to content</a>
{header(prefix, False)}
<main id="main">
<article class="{doc_class}">
{back}<h1>{h1}</h1>
{up}{body.strip()}
</article>
</main>
{footer(prefix)}
</body>
</html>
'''
    (ROOT / path).write_text(out)


GH = "https://github.com/AlexGromer"
ADV = GH + "/alexgromer.github.io/security/advisories/new"

PAGES = []

PAGES.append(dict(path="security.html", title="Security policy - Alex Gromer",
  desc="How to report a vulnerability in Alex Gromer's repositories or site: scope, private advisories, response targets, safe harbour.",
  h1="Security policy", body=f'''
<p>I take reports seriously and handle them as a person with a day job would: promptly when I can, openly about the limits. This policy covers every repository owned by <a href="{GH}" rel="noopener">AlexGromer</a> that is not a fork, and this website. For a fork, report to the upstream project.</p>

<h2>Report privately</h2>
<ul>
  <li>Use GitHub's private vulnerability reporting: open the <strong>Security</strong> tab of the affected repository and choose <em>Report a vulnerability</em>. For this site use <a href="{ADV}" rel="noopener">this form</a>.</li>
  <li>Please do not open a public issue or pull request for a vulnerability.</li>
  <li>Include the repository, version or commit, steps to reproduce, and the impact you see. Do not include other people's secrets or personal data.</li>
</ul>
<p>A machine-readable copy of this is in <a href="/.well-known/security.txt">/.well-known/security.txt</a>.</p>

<h2>What to expect</h2>
<p>These are targets for personal projects, not a service-level agreement.</p>
<ul>
  <li>Acknowledgement within 7 days.</li>
  <li>First assessment within 14 days: confirmed, not reproducible, or out of scope.</li>
  <li>A fix or a mitigation plan within 90 days. Coordinated disclosure: I publish an advisory once a fix is out, or after 90 days, whichever comes first, and I will agree a date with you if more time is needed.</li>
  <li>Credit in the advisory if you want it.</li>
</ul>

<h2>Supported versions</h2>
<p>The latest release, or the default branch where there are no releases. See <a href="support.html">support and maintenance</a>.</p>

<h2>No bounty</h2>
<p>I do not run a bounty programme and cannot pay for reports. I can say thanks in public.</p>

<h2>Scope</h2>
<ul>
  <li>In scope: the code, scripts, workflows and published releases in my non-fork repositories, and this website.</li>
  <li>Out of scope: my home network and servers (do not probe them), social engineering, denial of service, findings in third-party platforms such as GitHub itself, and reports about a dependency without a demonstrated effect on the project.</li>
</ul>

<h2>Safe harbour</h2>
<p>If you act in good faith, stay inside the scope above, avoid privacy violations, data destruction and service disruption, and give me reasonable time to fix the problem before you disclose it, I will not take legal action against you or report you for the research. I can only speak for myself, not for GitHub or other third parties.</p>
'''))

PAGES.append(dict(path="contributing.html", title="Contributing - Alex Gromer",
  desc="How to contribute to Alex Gromer's repositories: issues, small focused pull requests, signed commits, tests and review expectations.",
  h1="Contributing", body=f'''
<p>Thank you for considering a contribution. These rules apply to every repository under <a href="{GH}" rel="noopener">AlexGromer</a>. If a repository has its own <code>CONTRIBUTING</code> file, that file wins.</p>

<h2>Before you start</h2>
<ul>
  <li>Search the existing issues and pull requests first.</li>
  <li>For anything larger than a typo or an obvious fix, open an issue and describe the problem before writing code. It saves us both time.</li>
  <li>Security problems do not belong in public issues: see the <a href="security.html">security policy</a>.</li>
</ul>

<h2>Pull requests</h2>
<ul>
  <li>Small and focused: one concern per pull request, no drive-by reformatting, no unrelated fixes. Mention side findings separately.</li>
  <li>Prefer the simple solution that works over the complete one that does not ship (worse is better).</li>
  <li>Add or update tests. Run the project's checks locally. A failing test means the code is wrong; do not skip or disable tests to get green.</li>
  <li>Never commit secrets, tokens or personal data.</li>
</ul>

<h2>Commits</h2>
<ul>
  <li>Sign your commits (GPG or SSH signature). Where a repository enforces it, unsigned commits are not merged.</li>
  <li>Write the subject in the imperative, and explain why the change is needed, not only what it does.</li>
  <li>Keep history readable; I may ask you to squash or reorder.</li>
</ul>

<h2>Review</h2>
<ul>
  <li>I review on a best-effort basis and aim for a first answer within 7 days. There is no guarantee.</li>
  <li>I may ask you to narrow the scope, split the change, or take another approach. The maintainer's decision is final, and I will say why.</li>
  <li>A pull request with no activity for 30 days after a review may be closed; you are welcome to reopen it.</li>
</ul>

<h2>Licence of contributions</h2>
<p>Your contribution is licensed under the licence of the repository you contribute to. By opening a pull request you confirm you have the right to do that.</p>

<h2>Behaviour</h2>
<p>Everyone taking part is expected to follow the <a href="conduct.html">code of conduct</a>.</p>
'''))

PAGES.append(dict(path="conduct.html", title="Code of conduct - Alex Gromer",
  desc="The code of conduct for Alex Gromer's repositories and site: expected behaviour, what is not acceptable and how it is enforced.",
  h1="Code of conduct", body=f'''
<p>I want my repositories to be places where people can report a bug, ask a question or send a patch without having a bad time. This applies to issues, pull requests, discussions, comments and any other space tied to a repository under <a href="{GH}" rel="noopener">AlexGromer</a>.</p>

<h2>Expected</h2>
<ul>
  <li>Be respectful and assume good faith. Disagree with the idea, not the person.</li>
  <li>Be concrete and patient: give a way to reproduce, explain your reasoning, accept that maintainers have limited time.</li>
  <li>Accept a "no" on scope or direction gracefully. Forking is always an option.</li>
</ul>

<h2>Not acceptable</h2>
<ul>
  <li>Harassment, insults, threats, discriminatory language or imagery.</li>
  <li>Publishing other people's private information.</li>
  <li>Sustained disruption of discussions, spam or advertising.</li>
  <li>Anything else that would reasonably be seen as inappropriate in a professional setting.</li>
</ul>

<h2>Enforcement</h2>
<p>As the maintainer I may edit, hide or delete comments, lock threads, close pull requests, and block people from my repositories. Typical steps are a warning, a temporary block, and a permanent block for serious or repeated cases. I decide, and I will explain the decision when it is safe to do so.</p>

<h2>Reporting</h2>
<ul>
  <li>Use GitHub's own tools: <em>Report content</em> on the comment, or the <a href="https://github.com/contact/report-abuse" rel="noopener">report abuse form</a> for a user. I act on what I see and on what GitHub passes on.</li>
  <li>If you are not sure whether something crosses the line, say so in the thread without naming anyone, and I will look.</li>
  <li>Reports are handled in confidence as far as the platform allows. Retaliation against someone who reports in good faith is itself a violation.</li>
</ul>
'''))

PAGES.append(dict(path="support.html", title="Support and maintenance - Alex Gromer",
  desc="Maintenance and support policy for Alex Gromer's repositories: best effort, no SLA, supported versions, deprecation notice, archived repositories.",
  h1="Support and maintenance", body=f'''
<p>My repositories are personal projects that I publish because they may be useful to someone else. This page says what you can and cannot expect.</p>

<h2>Best effort, no SLA</h2>
<p>I answer issues and pull requests when I can. There is no response-time guarantee, no commercial support and no promise that a feature request will be accepted. If you depend on a project, pin a version and be ready to fork.</p>

<h2>What is supported</h2>
<ul>
  <li>The latest release, or the default branch where a repository has no releases.</li>
  <li>Older versions are not patched. Upgrade first, then report the problem again if it persists.</li>
  <li>Security fixes follow the <a href="security.html">security policy</a>.</li>
</ul>

<h2>Reporting a bug</h2>
<p>Open an issue in the repository with the version or commit, what you did, what you expected and what happened. A minimal reproduction is worth more than a long description. Changes you want to make yourself: see <a href="contributing.html">contributing</a>.</p>

<h2>Status of a repository</h2>
<ul>
  <li><strong>Active</strong>: developed and answered regularly.</li>
  <li><strong>Maintenance</strong>: fixes and security updates only.</li>
  <li><strong>Archived</strong>: read-only on GitHub, not maintained, no fixes of any kind. You may fork it under its licence.</li>
</ul>
<p>The status is stated in the repository's README when it is not Active.</p>

<h2>Deprecation notice</h2>
<p>When I plan to remove a feature or retire a project I announce it in the README and the release notes at least 30 days before the change where that is possible, and name the replacement if there is one.</p>

<h2>rclone-colab</h2>
<p><a href="rclone-colab.html">rclone-colab</a> is a single-user application for my own account. It is not offered to anyone else and has no support.</p>
'''))

PAGES.append(dict(path="licence.html", title="Licence - Alex Gromer",
  desc="The source of alexgromer.github.io is released under the MIT licence, copyright 2026 Alex Gromer.",
  h1="Licence", body=f'''
<p>The source of this website (HTML, CSS, JavaScript, scripts and images in the repository <a href="{GH}/alexgromer.github.io" rel="noopener">alexgromer.github.io</a>) is released under the MIT licence. The same text is in the <a href="LICENSE">LICENSE</a> file.</p>

<pre class="callout" tabindex="0">MIT License

Copyright (c) 2026 Alex Gromer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</pre>

<h2>Other repositories</h2>
<p>Each repository states its own licence in its <code>LICENSE</code> file. Where there is none, I do not grant one, and the default copyright rules apply.</p>

<h2>Names and marks</h2>
<p>Names of third-party projects and products on this site belong to their owners and are used only to say what my work relates to.</p>
'''))

PAGES.append(dict(path="privacy-site.html", title="Privacy of this site - Alex Gromer",
  desc="alexgromer.github.io collects nothing: no analytics, no cookies, no third-party requests. The only stored value is your theme choice, on your device.",
  h1="Privacy of this site", body=f'''
<p><strong>This site collects nothing.</strong> This page is about the website only. The policy for the rclone-colab application is a separate document: <a href="privacy.html">rclone-colab privacy policy</a>.</p>

<h2>What the site does not do</h2>
<ul>
  <li>No analytics, no tracking pixels, no fingerprinting.</li>
  <li>No cookies.</li>
  <li>No forms, accounts or comments.</li>
  <li>No third-party requests: fonts, scripts, styles and images are served from this site, and a content security policy forbids anything else.</li>
</ul>

<h2>What is stored on your device</h2>
<p>If you use the theme button, the site stores one value, <code>theme</code> (<code>light</code> or <code>dark</code>), in your browser's local storage so the choice survives a reload. It never leaves your device and I cannot read it. Clear your site data to remove it.</p>

<h2>Hosting</h2>
<p>The site is served by GitHub Pages. As the host, GitHub processes technical request data such as your IP address and browser details under its own <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">Privacy Statement</a>. I do not receive those logs and have no access to them.</p>

<h2>Links to other sites</h2>
<p>Links lead to GitHub and a few other sites. Once you follow one, that site's policy applies.</p>

<h2>Changes and contact</h2>
<p>Changes are published here with a new date. Questions: through <a href="{GH}" rel="noopener">GitHub</a>.</p>
'''))

# --- rclone-colab pages: restyled, substance unchanged -----------------------
PAGES.append(dict(path="rclone-colab.html", title="rclone-colab",
  desc="rclone-colab: a personal OAuth application by Alex Gromer that lets the owner's rclone synchronise one Google Drive folder with compute sessions the owner starts.",
  h1="rclone-colab", updated=False, body='''
<p class="updated">A personal, single-user application by <a href="index.html">Alex Gromer</a>.</p>

<h2>What rclone-colab does</h2>
<p>rclone-colab is an OAuth client for Google Drive used by one person: the developer. It lets the developer's own copy of
<a href="https://rclone.org/" rel="noopener">rclone</a>, running inside a Google Colab runtime or on the developer's workstation, read and
write files in the developer's own Google Drive folder. Its only job is to keep model evaluation runs, checkpoints and logs
in that folder without granting Drive access by hand every time a compute session starts.</p>
<ul>
  <li>Purpose: synchronise one Google Drive folder of the account owner with compute sessions the owner starts.</li>
  <li>Users: the account owner only. The application is not offered to third parties.</li>
  <li>Data: files in the owner's Google Drive, accessed under the <code>drive</code> scope, on the owner's instruction.</li>
</ul>

<h2>Who can use it</h2>
<p>Only the developer's Google account. The application is not offered, sold or distributed to anyone else.</p>

<h2>Data it accesses</h2>
<ul>
  <li>Files in the authorising account's Google Drive, under the <code>https://www.googleapis.com/auth/drive</code> scope,
  on the developer's instruction and within one folder the developer chooses.</li>
  <li>OAuth tokens issued by Google, stored only in the developer's own password manager and Colab Secrets.</li>
</ul>
<p>No data is shared with third parties, used for advertising, or used to train models.
Details: <a href="privacy.html">privacy policy</a> and <a href="terms.html">terms of service</a>.</p>

<h2>Revoking access</h2>
<p>At any time at <a href="https://myaccount.google.com/permissions" rel="noopener">myaccount.google.com/permissions</a>.</p>
'''))

PAGES.append(dict(path="privacy.html", title="Privacy policy — rclone-colab",
  desc="Privacy policy of the rclone-colab application by Alex Gromer.",
  h1="Privacy policy", updated=False, body='''
<p class="updated">Application: <strong>rclone-colab</strong>. Developer: Alex Gromer. Effective date: 30 October 2026.</p>

<h2>1. What the application is</h2>
<p>rclone-colab is a personal OAuth client used by the developer's own instance of rclone to access the developer's own Google Drive
from compute sessions the developer starts (for example Google Colab runtimes). It is a single-user tool: the only Google account
that authorises it is the developer's account. It is not distributed to, and must not be used by, other people.</p>

<h2>2. Data the application accesses</h2>
<ul>
  <li><strong>Google Drive files.</strong> With the <code>https://www.googleapis.com/auth/drive</code> scope the application can list,
  read, create, update and delete files in the authorising account's Google Drive. In practice it works inside one folder chosen by the
  developer (model evaluation runs, checkpoints, logs, result summaries).</li>
  <li><strong>OAuth tokens.</strong> The access and refresh tokens issued by Google are stored only in places controlled by the developer:
  a password manager on the developer's workstation and the Secrets store of the developer's Google Colab account. They are never written
  into notebooks, repositories, logs or shared files.</li>
  <li><strong>Basic account information</strong> that Google returns as part of the OAuth flow (account identifier). Nothing else is requested.</li>
</ul>

<h2>3. How the data is used</h2>
<p>Drive data is used exclusively to synchronise files between the developer's Drive folder and the developer's compute sessions.
No data is analysed for advertising, profiling or any purpose other than the file transfer the developer requests.</p>

<h2>4. Sharing and third parties</h2>
<p>No Google user data is sold, shared, transferred or disclosed to any third party. No third-party services receive the data.
The application does not use Google user data to develop, improve or train machine-learning models, and does not transfer
Google user data to any AI model.</p>

<h2>5. Storage and retention</h2>
<p>The application itself stores nothing except the OAuth tokens described above. Files remain in the developer's Google Drive and on the
compute sessions for as long as the developer keeps them; the developer can delete them at any time through Google Drive.
Tokens can be revoked at any time at <a href="https://myaccount.google.com/permissions" rel="noopener">myaccount.google.com/permissions</a>,
which immediately ends all access.</p>

<h2>6. Security</h2>
<p>Tokens are kept in encrypted stores (a password manager and Colab Secrets) with access limited to the developer's accounts. Transfers
use HTTPS to Google's APIs only.</p>

<h2>7. Google API Services User Data Policy</h2>
<p>The application's use of information received from Google APIs adheres to the
<a href="https://developers.google.com/terms/api-services-user-data-policy" rel="noopener">Google API Services User Data Policy</a>,
including the Limited Use requirements.</p>

<h2>8. Changes and contact</h2>
<p>Changes to this policy are published on this page with a new effective date. Questions: through
<a href="https://github.com/AlexGromer" rel="noopener">GitHub</a>. See also the <a href="terms.html">terms of service</a> and the
<a href="rclone-colab.html">application page</a>.</p>
'''))

PAGES.append(dict(path="terms.html", title="Terms of service — rclone-colab",
  desc="Terms of service of the rclone-colab application by Alex Gromer.",
  h1="Terms of service", updated=False, body='''
<p class="updated">Application: <strong>rclone-colab</strong>. Developer: Alex Gromer. Effective date: 30 October 2026.</p>

<h2>1. Scope</h2>
<p>rclone-colab is a personal, single-user OAuth client operated by the developer for the developer's own Google account.
It is provided for the developer's own use and is not offered as a service to anyone else.</p>

<h2>2. Use</h2>
<p>The application is used only to move files between the developer's Google Drive and compute sessions the developer starts.
Any other use is outside these terms.</p>

<h2>3. No warranty</h2>
<p>The application is provided "as is", without warranty of any kind. The developer is the only user and bears all responsibility
for the data handled with it.</p>

<h2>4. Google</h2>
<p>Use of Google Drive through this application is subject to Google's own terms. Access can be revoked at any time at
<a href="https://myaccount.google.com/permissions" rel="noopener">myaccount.google.com/permissions</a>.</p>

<h2>5. Changes and contact</h2>
<p>Changes are published on this page with a new effective date. Contact: through
<a href="https://github.com/AlexGromer" rel="noopener">GitHub</a>. See also the <a href="privacy.html">privacy policy</a> and the
<a href="rclone-colab.html">application page</a>.</p>
'''))


def not_found():
    body = f'''<div class="notfound">
<p class="big" aria-hidden="true">404</p>
<h1>Page not found</h1>
<p class="muted">The page you asked for does not exist or has moved.</p>
<div class="btns" style-free>
<a class="btn btn-primary" href="/">Go to the home page</a>
</div>
<p><a href="/#policies">Policies</a> &middot; <a href="/#projects">Projects</a> &middot; <a href="https://github.com/AlexGromer" rel="noopener">GitHub</a></p>
</div>'''.replace(" style-free", "")
    out = f'''{head("Page not found - Alex Gromer", "The page was not found on alexgromer.github.io.", "404.html", "/", True)}
<body>
<a class="skip" href="#main">Skip to content</a>
{header("/", False)}
<main id="main">
{body}
</main>
{footer("/")}
</body>
</html>
'''
    (ROOT / "404.html").write_text(out)


def patch_index():
    p = ROOT / "index.html"
    text = p.read_text()
    for name, body in (("header", header("", True)), ("footer", footer(""))):
        pat = re.compile(r"(<!-- gen:%s:start -->\n)(.*?)(\n<!-- gen:%s:end -->)" % (name, name), re.S)
        if not pat.search(text):
            sys.exit("marker gen:%s missing in index.html" % name)
        text = pat.sub(lambda m: m.group(1) + body + m.group(3), text)
    p.write_text(text)


def main():
    for spec in PAGES:
        page(**spec)
    not_found()
    patch_index()
    print("generated %d pages + 404.html, patched index.html" % len(PAGES))


if __name__ == "__main__":
    main()
