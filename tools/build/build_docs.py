"""Build the documentation site from the Markdown pages in wiki/.

The .md files in wiki/ are the only source. This script turns them into HTML pages
styled like the landing page, copies the hand-written files in docs/ (index.html,
docs.css, images) next to them, and writes the result to _site/ for GitHub Pages.
The page order and the sidebar groups come from wiki/_Sidebar.md.

It fails, with a list of problems, if a page links to a page, anchor or image that
does not exist, so a broken link is caught before it is published.

Usage:
    python tools/build/build_docs.py            # build into _site/
    python tools/build/build_docs.py --out DIR  # build somewhere else
"""
import argparse
import html
import re
import shutil
import sys
from pathlib import Path

import markdown
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent.parent
WIKI = ROOT / "wiki"
STATIC = ROOT / "docs"
SITE_URL = "https://phabzlabs.github.io/digital-rain/"
RAW_IMAGES = "https://github.com/phabzlabs/digital-rain/raw/main/docs/"


# ---------- page list ----------

def read_sidebar():
    """Return [(group or None, [page names])] from _Sidebar.md, in order."""
    groups, current = [], None
    for line in (WIKI / "_Sidebar.md").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        links = re.findall(r"\[\[([^\]|]+)\]\]", line)
        if line.startswith(("*", "-")) and links:
            if current is None:
                current = (None, [])
                groups.append(current)
            current[1].append(links[0])
        elif links:
            continue  # the [[Home]] line
        else:
            current = (line, [])
            groups.append(current)
    return [g for g in groups if g[1]]


def slug(name):
    return "docs.html" if name == "Home" else name.lower() + ".html"


def label(name):
    return "Docs home" if name == "Home" else name.replace("-", " ")


# ---------- Markdown to HTML ----------

def prepare(md):
    md = re.sub(r"\[\[([^\]|]+)\]\]", lambda m: f"[{label(m.group(1))}]({slug(m.group(1))})", md)
    md = md.replace(RAW_IMAGES, "")  # images live beside the pages
    md = md.replace(SITE_URL + "#", "index.html#").replace(SITE_URL, "index.html")
    return md


def figure(img, caption=None):
    src, alt = img.get("src", ""), img.get("alt", "")
    size = image_size(STATIC / src)
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    cap = caption if caption is not None else alt
    capt = f"<figcaption>{html.escape(cap)}</figcaption>" if cap else ""
    cls = ' class="narrow"' if src == "screenshot-settings.png" else ""
    return (f'<figure{cls}><img src="{html.escape(src)}" alt="{html.escape(alt)}"{dims} '
            f'loading="lazy">{capt}</figure>')


def image_size(path):
    """Width and height of a PNG or GIF, read from its header, or None."""
    try:
        head = path.read_bytes()[:32]
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
    if head[:4] == b"GIF8":
        return int.from_bytes(head[6:8], "little"), int.from_bytes(head[8:10], "little")
    return None


def convert(name):
    md = prepare((WIKI / f"{name}.md").read_text(encoding="utf-8"))
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    soup = BeautifulSoup(body, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text() if h1 else label(name)
    if h1:
        h1.decompose()
    first = soup.find(True, recursive=False)
    if first and first.name == "p" and not first.find("img"):
        first["class"] = "lead"
    for t in soup.find_all("table"):
        cells = t.find_all("td")
        heads = [th.get_text(strip=True) for th in t.find_all("th")]
        if cells and all(c.find("img") and not c.get_text(strip=True) for c in cells):
            figs = [figure(c.find("img"), heads[i] if i < len(heads) else None)
                    for i, c in enumerate(cells)]
            t.replace_with(BeautifulSoup(f'<div class="figs">{"".join(figs)}</div>', "html.parser"))
        elif heads[:1] == ["Page"]:
            items = []
            for tr in t.find("tbody").find_all("tr"):
                a, d = tr.find_all("td")[:2]
                items.append(f"<li>{a.decode_contents()}<span>{d.decode_contents()}</span></li>")
            listing = f'<ul class="pagelist">{"".join(items)}</ul>'
            t.replace_with(BeautifulSoup(listing, "html.parser"))
    for p in soup.find_all("p"):
        imgs = p.find_all("img")
        if len(imgs) == 1 and not p.get_text(strip=True):
            p.replace_with(BeautifulSoup(figure(imgs[0]), "html.parser"))
    for t in soup.find_all("table"):
        t.wrap(soup.new_tag("div", attrs={"class": "table-wrap"}))
    toc = []
    for h in soup.find_all(["h2", "h3"]):
        hid = h.get("id")
        if not hid:
            continue
        if h.name == "h2":
            toc.append((hid, h.get_text()))
        a = soup.new_tag("a", href=f"#{hid}",
                         attrs={"class": "anchor", "aria-label": f"Link to {h.get_text()}"})
        a.string = "#"
        h.append(a)
    return title, str(soup), toc


# ---------- page template ----------

FOOTER = """<footer>
  <div class="wrap">
    <span>Made by <a href="https://github.com/phabzlabs">phabzlabs</a>, based on
      <a href="https://github.com/madkoding/matrix-screensaver">madkoding's original</a>.</span>
    <span class="links">
      <a href="https://github.com/phabzlabs/digital-rain">Source code</a>
      <a href="https://github.com/phabzlabs/digital-rain/issues">Report a problem</a>
      <a href="https://github.com/phabzlabs/digital-rain/blob/main/LICENSE">GPL-3.0 licence</a>
    </span>
    <span>Digital Rain is an unofficial, Matrix-inspired fan project,
      not affiliated with or endorsed by Warner Bros.</span>
    <span>Optional upscaling based on
      <a href="https://github.com/GPUOpen-Effects/FidelityFX-FSR">AMD FidelityFX Super Resolution
      1.0</a> (MIT).</span>
  </div>
</footer>"""


def sidebar(groups, current):
    cur = ' aria-current="page"'
    out = [f'<a class="home" href="docs.html"{cur if current == "Home" else ""}>Docs home</a>']
    for i, (grp, pages) in enumerate(groups):
        out.append(f'<p class="grp" id="g{i}">{html.escape(grp or "")}</p>')
        out.append(f'<ul aria-labelledby="g{i}">')
        for p in pages:
            mark = cur if p == current else ""
            out.append(f'<li><a href="{slug(p)}"{mark}>{label(p)}</a></li>')
        out.append("</ul>")
    return "\n".join(out)


def description(md_text):
    for para in md_text.split("\n\n")[1:]:
        para = para.strip()
        if para and not para.startswith(("!", "|", "#", "```")):
            text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: label(m.group(1)), para)
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text).replace("`", "")
            return text if len(text) <= 200 else text[:197].rsplit(" ", 1)[0] + "..."
    return "Digital Rain documentation"


def render(name, groups, order):
    title, body, toc = convert(name)
    i = order.index(name)
    pager = '<nav class="pager" aria-label="Previous and next page">'
    if i > 0:
        prev = order[i - 1]
        pager += f'<a class="prev" href="{slug(prev)}"><span>Previous</span>{label(prev)}</a>'
    if i < len(order) - 1:
        nxt = order[i + 1]
        pager += f'<a class="next" href="{slug(nxt)}"><span>Next</span>{label(nxt)}</a>'
    pager += "</nav>"
    grp = next((g for g, ps in groups if name in ps), None)
    crumb = ""
    if grp:
        crumb = f'<p class="crumb"><a href="docs.html">Docs</a> / {html.escape(grp)}</p>'
    toc_html = "<div></div>"
    if len(toc) > 1:
        toc_html = ('<aside class="toc" aria-label="On this page"><p>On this page</p><ul>'
                    + "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc)
                    + "</ul></aside>")
    side = sidebar(groups, name)
    doc_title = "Digital Rain documentation"
    if name != "Home":
        doc_title = f"{title} | {doc_title}"
    desc = description((WIKI / f"{name}.md").read_text(encoding="utf-8"))
    canonical = SITE_URL + slug(name)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(doc_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="color-scheme" content="dark">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="docs.css">
</head>
<body>
<div class="wrap">
  <header class="top">
    <a class="brand" href="index.html">Digital<span>Rain</span></a>
    <nav class="site" aria-label="Site">
      <a class="hide-sm" href="index.html#features">Features</a>
      <a class="hide-sm" href="index.html#install">Install</a>
      <a href="docs.html" aria-current="page">Docs</a>
      <a class="hide-sm" href="https://github.com/phabzlabs/digital-rain">GitHub</a>
    </nav>
  </header>
  <div class="docs">
    <nav class="side" aria-label="Documentation">
{side}
    </nav>
    <main>
      <details class="menu"><summary>Docs menu</summary>
        <nav class="side" aria-label="Documentation, compact">{side}</nav>
      </details>
      <article>
        {crumb}
        <h1>{html.escape(title)}</h1>
{body}
        {pager}
      </article>
    </main>
    {toc_html}
  </div>
</div>
{FOOTER}
</body>
</html>
"""


# ---------- link check ----------

def check_links(out):
    problems = []
    ids = {}
    for f in out.glob("*.html"):
        soup = BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser")
        ids[f.name] = {t["id"] for t in soup.find_all(id=True)}
    for f in out.glob("*.html"):
        soup = BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.match(r"^[a-z]+:", href):
                continue
            page, _, frag = href.partition("#")
            page = page or f.name
            if page not in ids:
                problems.append(f"{f.name}: link to missing page {href}")
            elif frag and frag not in ids[page]:
                problems.append(f"{f.name}: link to missing anchor {href}")
        for img in soup.find_all("img", src=True):
            if not re.match(r"^[a-z]+:", img["src"]) and not (out / img["src"]).exists():
                problems.append(f"{f.name}: missing image {img['src']}")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "_site"))
    out = Path(ap.parse_args().out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(STATIC, out)
    groups = read_sidebar()
    order = ["Home"] + [p for _, ps in groups for p in ps]
    missing = [p for p in order if not (WIKI / f"{p}.md").exists()]
    if missing:
        sys.exit(f"Pages named in _Sidebar.md have no .md file: {', '.join(missing)}")
    unlisted = sorted(f.stem for f in WIKI.glob("*.md")
                      if f.stem not in order and not f.stem.startswith("_"))
    if unlisted:
        print(f"Note: not in _Sidebar.md, so not published: {', '.join(unlisted)}")
    for name in order:
        (out / slug(name)).write_text(render(name, groups, order), encoding="utf-8")
    problems = check_links(out)
    if problems:
        print("\n".join(problems))
        sys.exit(f"{len(problems)} broken link(s). Fix them before publishing.")
    print(f"Built {len(order)} pages into {out}")


if __name__ == "__main__":
    main()
