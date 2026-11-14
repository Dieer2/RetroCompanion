"""Builds the Guides section of the website from the articles in docs/guides/*.md.

    python tools/make_guides.py

Writes site/guides.html (the list), site/guides/<name>.html (one per article) and
site/sitemap.xml. Standard library only. An article starts with "title:", "description:"
and "date:" lines, then a blank line, then a small subset of Markdown: "## " headings,
paragraphs, "- " and "1. " lists, tables with | and [text](address) links.

A line that starts with "::" places a figure or an interactive tool (see BLOCKS). The
figures are drawn here from the plugin's own numbers; the tools are run by site/guides.js.
Coordinates such as (9, 6) and code addresses such as $EDBB are set in mono: the site's
signature detail (see companion/theme.py).
"""
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import games.dragon_warrior as DW       # noqa: E402  (only constants: no ROM data is read or written)

BASE = "https://retro.dieergames.hu"
MONTHS = ("January February March April May June July August September October November December").split()
ORDER = ["dragon-warrior-walkthrough", "dragon-warrior-hidden-items", "dragon-warrior-levels-spells",
         "dragon-warrior-shops-prices", "dragon-warrior-game-code-facts", "dragon-warrior-history"]
NAV = ('<a href="/#features">Features</a><a href="/guides">Guides</a><a href="/#leaderboard">Leaderboard</a>'
       '<a href="/support">Support</a><a href="/privacy">Privacy</a>')
COST = dict(zip(DW.SPELL_ORDER, [4, 2, 2, 3, 2, 6, 8, 2, 10, 5]))
TOWNS = ["Brecconary", "Garinham", "Kol", "Rimuldar", "Cantlin"]
# places on the 120 x 120 overworld: name, x, y, kind ("town", "cave", "hidden")
PLACES = [("Tantegel Castle", 43, 43, "home"), ("Brecconary", 48, 41, "town"), ("Garinham", 2, 2, "town"),
          ("Kol", 104, 10, "town"), ("Rimuldar", 102, 72, "town"), ("Cantlin", 73, 102, "town"),
          ("Hauksness", 25, 89, "town"), ("Charlock Castle", 48, 48, "cave"), ("Erdrick's Cave", 28, 12, "cave"),
          ("Swamp Cave", 104, 44, "cave"), ("Northern Shrine", 81, 1, "cave"), ("Southern Shrine", 108, 109, "cave"),
          ("Erdrick's Token", 83, 113, "hidden"), ("Rainbow Bridge", 65, 49, "hidden")]

# where a label sits when the default (right of its mark) would run into a neighbour: (left side?, y shift)
LABEL = {"Tantegel Castle": (True, 4), "Brecconary": (False, -3), "Charlock Castle": (True, 14), "Rainbow Bridge": (False, 12),
         "Southern Shrine": (True, -2), "Erdrick's Token": (True, 10)}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{ogtype}">
<meta property="og:site_name" content="Retro Companion">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{base}/img/share.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/img/favicon.png">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header class="bar">
  <a class="mark" href="/"><img src="/img/dieergames.png" width="203" height="22" alt="DieerGames"></a>
  <nav>{nav}</nav>
</header>
<main class="doc article">
{body}
</main>
<footer>
  <p>Retro Companion has no connection to Square Enix or Nintendo. Game names belong to their owners.
    This site does not distribute ROMs.</p>
  <p><a href="/">Home</a> · <a href="/guides">Guides</a> · <a href="/news">What's new</a> · <a href="/support">Support</a> · <a href="/privacy">Privacy</a></p>
</footer>{scripts}
<script src="/motion.js" defer></script>
<script src="/hit.js" defer></script>
</body>
</html>
"""


# -- figures, drawn from the numbers ---------------------------------------------
def fig_xp():
    W, H, L, R, T, B = 640, 280, 56, 16, 16, 36
    xs = lambda lv: L + (W - L - R) * (lv - 1) / 29.0
    ys = lambda xp: H - B - (H - T - B) * xp / 65535.0
    grid = "".join('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/><text class="tick" x="%d" y="%.1f" text-anchor="end">%s</text>'
                   % (L, W - R, ys(v), ys(v), L - 8, ys(v) + 4, "{:,}".format(v)) for v in (0, 20000, 40000, 60000))
    ticks = "".join('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%d</text>' % (xs(lv), H - 12, lv)
                    for lv in (1, 5, 10, 15, 20, 25, 30))
    line = " ".join("%s%.1f %.1f" % ("M" if i == 0 else "L", xs(i + 1), ys(xp)) for i, xp in enumerate(DW.XP_TABLE))
    dots = "".join('<circle class="spell" cx="%.1f" cy="%.1f" r="3"><title>Level %d: %s</title></circle>'
                   % (xs(lv), ys(DW.XP_TABLE[lv - 1]), lv, name) for lv, name in sorted(DW.SPELLS.items()))
    return ('<figure class="fig" data-reveal><svg viewBox="0 0 %d %d" role="img" aria-label="Total experience needed for each level, 1 to 30">'
            '%s%s<path class="curve" pathLength="1" d="%s"/>%s<circle id="xp-you" class="you" r="5" cx="-20" cy="-20"/></svg>'
            '<figcaption>Total experience for each level. The dots are the levels where a spell is learned. '
            'From level 20 on every level costs 4,000 more.</figcaption></figure>') % (W, H, grid, ticks, line, dots)


def fig_world():
    S, K = 480, 4.0
    grid = "".join('<line class="grid" x1="%d" x2="%d" y1="0" y2="%d"/><line class="grid" x1="0" x2="%d" y1="%d" y2="%d"/>'
                   % (v, v, S, S, v, v) for v in range(0, S + 1, 80))
    tx, ty = 43 * K, 43 * K
    axes = '<line class="axis" x1="%d" x2="%d" y1="0" y2="%d"/><line class="axis" x1="0" x2="%d" y1="%d" y2="%d"/>' % (tx, tx, S, S, ty, ty)
    pts = []
    for name, x, y, kind in PLACES:
        cx, cy = x * K + 2, y * K + 2
        left, dy = LABEL.get(name, (x > 84, 4))
        mark = ('<rect x="%.1f" y="%.1f" width="9" height="9"/>' % (cx - 4.5, cy - 4.5) if kind == "hidden"
                else '<circle cx="%.1f" cy="%.1f" r="%s"/>' % (cx, cy, "5" if kind == "home" else "3.5"))
        pts.append('<g class="pt %s" tabindex="0" data-name="%s" data-x="%d" data-y="%d">%s'
                   '<text x="%.1f" y="%.1f" text-anchor="%s">%s</text></g>'
                   % (kind, html.escape(name), x, y, mark, cx + (-9 if left else 9), cy + dy, "end" if left else "start",
                      html.escape(name)))
    return ('<figure class="fig world" data-reveal><svg viewBox="-8 -8 %d %d" role="img" aria-label="Where the places of Alefgard lie, '
            'measured from Tantegel Castle">%s%s%s<g id="love-you" class="you" visibility="hidden"><circle r="6"/></g></svg>'
            '<figcaption id="world-note">Places on the overworld, 120 by 120 tiles. The two lines cross at Tantegel Castle, '
            'where the game counts from. Squares are hidden spots. Pick a place to read its distance.</figcaption></figure>'
            ) % (S + 16, S + 16, grid, axes, "".join(pts))


def fig_timeline():
    rows = [("1986", "Dragon Quest comes out for the Famicom in Japan"), ("1989", "Nintendo publishes it in North America as Dragon Warrior"),
            ("1990", "Nintendo Power sends the game to its subscribers"), ("2000", "The Game Boy Color port reaches North America"),
            ("2014", "A phone version is released worldwide"), ("2019", "The game comes to the Nintendo Switch"),
            ("2025", "The HD-2D remake is released")]
    return '<ol class="timeline" data-reveal>%s</ol>' % "".join(
        '<li><span class="mono">%s</span><span>%s</span></li>' % r for r in rows)


def tool_xp():
    return ('<div class="tool" data-tool="xp"><label for="xp-in">Your experience</label>'
            '<input id="xp-in" type="number" inputmode="numeric" min="0" max="65535" placeholder="1420">'
            '<p class="out" id="xp-out" aria-live="polite">Type the experience from your status screen</p>'
            '<div class="meter"><span id="xp-bar"></span></div></div>')


def tool_damage():
    f = lambda i, label, ph: '<div><label for="%s">%s</label><input id="%s" type="number" inputmode="numeric" min="0" max="255" placeholder="%s"></div>' % (i, label, i, ph)
    return ('<div class="tool" data-tool="damage"><div class="fields">%s%s%s%s</div>'
            '<p class="out" id="dmg-out" aria-live="polite">Fill in the four numbers. The example in the text uses 40 and 22</p></div>'
            ) % (f("d-atk", "Your attack power", "40"), f("d-edef", "Enemy defense", "22"),
                 f("d-eatk", "Enemy attack power", "28"), f("d-def", "Your defense power", "36"))


def tool_gold():
    opts = "".join("<option>%s</option>" % t for t in TOWNS)
    return ('<div class="tool" data-tool="gold"><div class="fields"><div><label for="g-in">Your gold</label>'
            '<input id="g-in" type="number" inputmode="numeric" min="0" max="65535" placeholder="1290"></div>'
            '<div><label for="g-town">Town</label><select id="g-town"><option value="">Every town</option>%s</select></div></div>'
            '<p class="out" id="g-out" aria-live="polite">Type your gold and the tables below dim what you cannot buy yet</p></div>') % opts


def tool_love():
    return ('<div class="tool" data-tool="love"><div class="fields">'
            '<div><label for="l-ns">Gwaelin says</label><input id="l-ns" type="number" inputmode="numeric" min="0" max="119" placeholder="70"></div>'
            '<div><label for="l-nsd">to the</label><select id="l-nsd"><option>south</option><option>north</option></select></div>'
            '<div><label for="l-ew">and</label><input id="l-ew" type="number" inputmode="numeric" min="0" max="119" placeholder="40"></div>'
            '<div><label for="l-ewd">to the</label><select id="l-ewd"><option>east</option><option>west</option></select></div></div>'
            '<p class="out" id="l-out" aria-live="polite">Type what Gwaelin\'s Love tells you and see how far the Token is</p></div>')


def image_overlay():
    return ('<figure class="fig shot"><img src="/img/overlay.png" width="440" height="883" loading="lazy" '
            'alt="The Retro Companion overlay at step 9: the guide, the hero\'s numbers and the map of Kol with the route to the flute">'
            '<figcaption>The overlay at step 9. The line on the map leads to the tile where the Fairy Flute is.</figcaption></figure>')


BLOCKS = {"figure xp": fig_xp, "figure world": fig_world, "figure timeline": fig_timeline, "tool xp": tool_xp,
          "tool damage": tool_damage, "tool gold": tool_gold, "tool love": tool_love, "image overlay": image_overlay}


# -- markdown ------------------------------------------------------------------
def mono(text):
    """Coordinates and code addresses in the site's mono face (text is already escaped)."""
    text = re.sub(r"\((\d{1,3}), (\d{1,3})\)", r'<span class="mono">(\1, \2)</span>', text)
    return re.sub(r"(\$[0-9A-F]{2,4})\b", r'<span class="mono">\1</span>', text)


def inline(text):
    out, pos = [], 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+(?:\([^)]*\))?[^)\s]*)\)", text):
        out.append(mono(html.escape(text[pos:m.start()], quote=False)))
        href = m.group(2)
        rel = ' rel="noopener"' if href.startswith("http") else ""
        out.append('<a href="%s"%s>%s</a>' % (html.escape(href), rel, html.escape(m.group(1), quote=False)))
        pos = m.end()
    out.append(mono(html.escape(text[pos:], quote=False)))
    return "".join(out)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md, steps=False):
    lines, out, i = md.split("\n"), [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
        elif ln.startswith("::"):
            out.append("  " + BLOCKS[ln[2:].strip()]())
            i += 1
        elif ln.startswith("## "):
            out.append("  <h2>%s</h2>" % inline(ln[3:].strip()))
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            num = [all(re.match(r"^[\d,. ]*$", r[c]) for r in body if c < len(r)) for c in range(len(head))]
            cls = lambda c: ' class="num"' if num[c] and c else ""
            out.append('  <div class="table"><table>\n    <thead><tr>%s</tr></thead>\n    <tbody>' % "".join(
                "<th%s>%s</th>" % (cls(c), inline(h)) for c, h in enumerate(head)))
            for r in body:
                out.append("      <tr>%s</tr>" % "".join("<td%s>%s</td>" % (cls(c), inline(v)) for c, v in enumerate(r)))
            out.append("    </tbody>\n  </table></div>")
        elif re.match(r"^(- |\d+\. )", ln):
            ordered = not ln.startswith("- ")
            first = int(re.match(r"^(\d+)", ln).group(1)) if ordered else 1
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            tag = "ol" if ordered else "ul"
            attr = (' start="%d"' % first if ordered and first != 1 else "") + (' class="steps"' if ordered and steps else "")
            out.append("  <%s%s>\n%s\n  </%s>" % (tag, attr, "\n".join("    <li>%s</li>" % inline(t) for t in items), tag))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(## |\||- |\d+\. |::)", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append("  <p>%s</p>" % inline(" ".join(para)))
    return "\n".join(out)


def load(path):
    text = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    head, _, body = text.partition("\n\n")
    meta = dict(ln.split(":", 1) for ln in head.split("\n"))
    return {k.strip(): v.strip() for k, v in meta.items()}, body


def main():
    arts = []
    for path in glob.glob(os.path.join(ROOT, "docs", "guides", "*.md")):
        meta, body = load(path)
        arts.append((os.path.splitext(os.path.basename(path))[0], meta, body))
    arts.sort(key=lambda a: ORDER.index(a[0]) if a[0] in ORDER else len(ORDER))
    os.makedirs(os.path.join(ROOT, "site", "guides"), exist_ok=True)
    esc = lambda s: html.escape(s, quote=True)
    data = {"xp": DW.XP_TABLE, "spells": {str(k): v for k, v in DW.SPELLS.items()}, "cost": COST,
            "token": [83, 113], "home": [43, 43]}
    scripts = ('\n<script type="application/json" id="rc-data">%s</script>\n<script src="/guides.js" defer></script>'
               % json.dumps(data, separators=(",", ":")))
    for slug, meta, body in arts:
        others = "".join('    <li><a href="/guides/%s">%s</a></li>\n' % (s, html.escape(m["title"], quote=False))
                         for s, m, _ in arts if s != slug)
        page = PAGE.format(
            title=esc(meta["title"]), desc=esc(meta["description"]), url="%s/guides/%s" % (BASE, slug), base=BASE,
            ogtype="article", nav=NAV, scripts=scripts,
            body='  <p class="crumb"><a href="/guides">Guides</a> · Dragon Warrior</p>\n  <h1>%s</h1>\n%s\n'
                 '  <h2>More guides</h2>\n  <ul class="more">\n%s  </ul>'
                 % (html.escape(meta["title"], quote=False), render(body, steps=slug.endswith("walkthrough")), others))
        with open(os.path.join(ROOT, "site", "guides", slug + ".html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page)
    row = lambda i, s, m: ('  <a class="guide%s" href="/guides/%s"><span class="mono">%02d</span><span><strong>%s</strong>'
                           '<em>%s</em></span></a>') % (" first" if i == 0 else "", s, i + 1,
                                                         html.escape(m["title"], quote=False), html.escape(m["description"], quote=False))
    listing = "\n".join(row(i, s, m) for i, (s, m, _) in enumerate(arts))
    desc = "Guides for Dragon Warrior on the NES: a 32-step walkthrough, hidden items, the level chart, shop prices and the rules read from the game's code."
    page = PAGE.format(title="Dragon Warrior guides · Retro Companion", desc=esc(desc), url=BASE + "/guides", base=BASE,
                       ogtype="website", nav=NAV, scripts="",
                       body='  <h1>Guides</h1>\n  <p class="lead">Written for Dragon Warrior on the NES, the first game Retro Companion supports. '
                            'The facts come from the game itself.</p>\n  <div class="guide-list">\n' + listing + "\n  </div>")
    with open(os.path.join(ROOT, "site", "guides.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    # what is new: the same list the program shows (companion/news.py)
    from companion.news import NEWS
    parts = []
    for n in NEWS:
        y, mo, d = n["date"].split("-")
        parts.append('  <section class="news">\n    <p class="mono"><time datetime="%s">%d %s %s</time></p>\n    <h2>%s</h2>\n    <ul>\n%s    </ul>\n  </section>'
                     % (n["date"], int(d), MONTHS[int(mo) - 1], y, html.escape(n["title"], quote=False),
                        "".join("      <li>%s</li>\n" % html.escape(it, quote=False) for it in n["items"])))
    desc = "What is new in Retro Companion and on its website, with dates: new versions of the program, guides and features."
    page = PAGE.format(title="What's new · Retro Companion", desc=esc(desc), url=BASE + "/news", base=BASE,
                       ogtype="website", nav=NAV, scripts="",
                       body='  <h1>What\'s new</h1>\n  <p class="lead">New things in the program and on this site, newest first. '
                            'The program shows the same list in its library window.</p>\n' + "\n".join(parts))
    with open(os.path.join(ROOT, "site", "news.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    urls = ["/", "/guides"] + ["/guides/" + s for s, _, _ in arts] + ["/news", "/support", "/privacy"]
    with open(os.path.join(ROOT, "site", "sitemap.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + "".join("  <url><loc>%s%s</loc></url>\n" % (BASE, u) for u in urls) + "</urlset>\n")
    print("%d guides written" % len(arts))


if __name__ == "__main__":
    main()
