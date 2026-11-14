"""Profile pictures: twenty small portraits drawn here in code, or the player's own image.

The built-in ones are 16 x 16 pixel portraits put together from a few parts (skin, hair cut,
head wear, one extra), so no picture file comes with the program. An own image is a PNG or
GIF (the two formats Tk reads by itself); it is copied next to the game data and never
leaves the computer. The choice lives in the settings as {"id": n} or {"file": path}.
"""
import os
import shutil

HOME = os.path.join(os.path.expanduser("~"), "RetroCompanion")
N = 16
SKIN = ("#f1c9a5", "#d9a57a", "#a8734d", "#70482f")
DARK = "#1b1917"

# name, hair cut, hair colour, skin, clothes, background, head wear, extra
BUILT_IN = [
    ("Squire", "short", "#6b4a2b", 0, "#7d8a99", "#2f3b45", None, None),
    ("Ranger", "short", "#3b2a1a", 1, "#4f7a4a", "#26352a", "hood", None),
    ("Knight", "short", "#2a2420", 0, "#9aa3ad", "#33363d", "helmet", None),
    ("Rogue", "spiky", "#1f1b18", 2, "#4a4458", "#2a2633", None, "patch"),
    ("Wizard", "short", "#c9c4bb", 1, "#4a5fa8", "#262c45", "hat", "beard"),
    ("Smith", "short", "#8a4b1e", 2, "#8a5a3c", "#3a2c22", None, "beard"),
    ("Scout", "short", "#d8b060", 0, "#b0683c", "#3d3024", "cap", None),
    ("Monk", "bald", "#000000", 3, "#c98a2b", "#3b301c", "band", None),
    ("Bard", "bob", "#c8742a", 0, "#a03c5a", "#3a2430", None, None),
    ("Prince", "short", "#e0c060", 1, "#7a3fa0", "#2e2440", "crown", None),
    ("Princess", "long", "#e6c765", 0, "#d06a9a", "#402a36", "crown", None),
    ("Archer", "tail", "#b8452a", 1, "#4f7a4a", "#26352a", None, None),
    ("Witch", "long", "#3a2a5a", 0, "#5a3f8a", "#2a2440", "hat", None),
    ("Healer", "long", "#7a5230", 2, "#e8e2d6", "#35393f", "hood", None),
    ("Warrior", "braids", "#d8a23c", 1, "#a04a3a", "#3d2a26", "band", None),
    ("Scholar", "bun", "#2a2420", 3, "#3f6a8a", "#243340", None, "glasses"),
    ("Dancer", "bob", "#1f1b18", 2, "#d0a02a", "#3d3320", None, "bow"),
    ("Corsair", "long", "#8a2f2a", 1, "#2f4a6a", "#222c3a", "band", "patch"),
    ("Druid", "long", "#4f8a4a", 3, "#6a5a3a", "#2c3324", None, "flower"),
    ("Paladin", "braids", "#c9c4bb", 0, "#c9b060", "#3a3526", "helmet", None),
]


def _shade(c, k):
    return "#%02x%02x%02x" % tuple(min(255, max(0, int(int(c[i:i + 2], 16) * k))) for i in (1, 3, 5))


def portrait(spec):
    """The 16 x 16 grid of colours of one built-in portrait."""
    name, cut, hair, skin, cloth, bg, wear, extra = spec
    skin = SKIN[skin]
    g = [[bg] * N for _ in range(N)]

    def box(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(N, y1 + 1)):
            for x in range(max(0, x0), min(N, x1 + 1)):
                g[y][x] = c

    if cut in ("long", "braids"):                   # hair behind the shoulders first
        box(3, 5, 12, 13 if cut == "long" else 11, hair)
    box(2, 13, 13, 15, cloth)                       # shoulders
    box(3, 13, 3, 13, bg)
    box(12, 13, 12, 13, bg)
    box(2, 13, 2, 13, bg)
    box(13, 13, 13, 13, bg)
    box(6, 14, 9, 15, _shade(cloth, 0.8))
    box(7, 12, 8, 13, _shade(skin, 0.85))           # neck
    box(4, 4, 11, 11, skin)                         # face, corners rounded
    for x, y in ((4, 4), (11, 4), (4, 11), (11, 11)):
        g[y][x] = hair if (cut in ("long", "braids") and y == 11) else bg
    g[7][6] = g[7][9] = DARK                        # eyes
    box(7, 10, 8, 10, _shade(skin, 0.7))            # mouth
    if cut != "bald":
        box(4, 2, 11, 4, hair)
        g[2][4] = g[2][11] = bg
        g[5][4] = g[5][11] = hair
    if cut == "spiky":
        for x in (4, 6, 8, 10):
            g[1][x] = hair
    elif cut == "bob":
        box(3, 3, 3, 9, hair)
        box(12, 3, 12, 9, hair)
        box(4, 5, 4, 9, hair)
        box(11, 5, 11, 9, hair)
    elif cut == "tail":
        box(12, 4, 13, 5, hair)
        box(13, 6, 13, 10, hair)
    elif cut == "bun":
        box(7, 0, 8, 1, hair)
    elif cut == "long":
        box(3, 3, 3, 12, hair)
        box(12, 3, 12, 12, hair)
    elif cut == "braids":
        box(3, 4, 3, 13, hair)
        box(12, 4, 12, 13, hair)
        g[9][3] = g[9][12] = g[12][3] = g[12][12] = _shade(hair, 0.7)
    if wear == "hood":
        box(3, 1, 12, 3, cloth)
        box(3, 4, 3, 12, cloth)
        box(12, 4, 12, 12, cloth)
        g[1][3] = g[1][12] = bg
        box(4, 4, 11, 4, _shade(cloth, 0.75))
    elif wear == "helmet":
        steel = "#aab2bd"
        box(3, 1, 12, 5, steel)
        g[1][3] = g[1][12] = bg
        box(3, 5, 12, 5, _shade(steel, 0.7))
        box(7, 6, 8, 8, steel)
        box(3, 6, 3, 9, steel)
        box(12, 6, 12, 9, steel)
    elif wear == "hat":
        felt = _shade(cloth, 0.8)
        box(2, 4, 13, 4, felt)
        box(4, 2, 11, 3, felt)
        box(6, 0, 9, 1, felt)
        box(4, 3, 11, 3, "#e3b84b")
    elif wear == "cap":
        box(4, 2, 11, 4, cloth)
        box(4, 5, 13, 5, _shade(cloth, 0.7))
    elif wear == "band":
        box(4, 4, 11, 4, "#c8452f")
        if cut != "bald":
            g[5][12] = "#c8452f"
    elif wear == "crown":
        gold = "#e3b84b"
        box(5, 2, 10, 2, gold)
        for x in (5, 7, 8, 10):
            g[1][x] = gold
        g[2][7] = "#c8452f" if cut != "long" else "#7fd6e0"
    if extra == "patch":
        g[7][9] = DARK
        box(8, 6, 10, 7, DARK)
        box(4, 5, 11, 5, DARK) if wear is None and cut != "long" else None
    elif extra == "beard":
        box(5, 9, 10, 11, hair)
        box(7, 10, 8, 10, _shade(skin, 0.7))
        box(6, 12, 9, 12, hair)
    elif extra == "glasses":
        for x in (5, 7, 8, 10):                     # two lenses and the bridge between them
            g[7][x] = "#cfd6de"
        g[7][4] = g[7][11] = "#8d939b"
    elif extra == "bow":
        box(9, 1, 12, 2, "#c8452f")
        g[1][10] = g[2][11] = _shade("#c8452f", 0.7)
    elif extra == "flower":
        g[3][10] = "#e3b84b"
        for x, y in ((9, 3), (11, 3), (10, 2), (10, 4)):
            g[y][x] = "#f1e9de"
    return g


def setting_ok(s):
    return isinstance(s, dict) and (("file" in s and os.path.isfile(str(s["file"]))) or
                                    (isinstance(s.get("id"), int) and 0 <= s["id"] < len(BUILT_IN)))


def name(setting):
    if setting_ok(setting) and "file" in setting:
        return "Own picture"
    return BUILT_IN[setting["id"] if setting_ok(setting) else 0][0]


def image(tk, setting, size):
    """A PhotoImage of the chosen picture, at most `size` pixels on its longer side."""
    if setting_ok(setting) and "file" in setting:
        try:
            img = tk.PhotoImage(file=setting["file"])
            big = max(img.width(), img.height())
            if big > size:
                img = img.subsample(-(-big // size))
            elif big * 2 <= size:
                img = img.zoom(size // big)
            return img
        except Exception:               # not a picture Tk can read any more: fall back to a built-in one
            pass
    g = portrait(BUILT_IN[setting["id"] if setting_ok(setting) and "id" in setting else 0])
    base = tk.PhotoImage(width=N, height=N)
    base.put(" ".join("{" + " ".join(row) + "}" for row in g))
    return base.zoom(max(1, size // N))


def keep(path):
    """Copy the player's own picture next to the game data. Returns the setting, or an error text."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".png", ".gif"):
        return "Choose a PNG or GIF picture"
    try:
        os.makedirs(HOME, exist_ok=True)
        dst = os.path.join(HOME, "avatar" + ext)
        if os.path.abspath(path) != os.path.abspath(dst):
            shutil.copyfile(path, dst)
    except OSError as exc:
        return "Could not copy the picture (%s)" % exc
    return {"file": dst}
