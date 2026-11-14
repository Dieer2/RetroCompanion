"""Design tokens and the few shared widgets, used by the library window and the overlay.

Direction (the rules follow "unslop" by Damir Sokolovsky (@heydamir), CC BY 4.0,
https://github.com/heydamir/unslop):

  Product    a game library that keeps a live walkthrough on top of the running game
  Character  pocket strategy guide: steady, exact, out of the way
  World      a printed game manual read at night: warm paper tones on a dark desk
  Moments    the live map in the overlay and the world-map strip on a game's page
  Signature  figures, coordinates and step numbers set in mono, like margin notes

So: one warm neutral ramp for every surface, three text roles, one accent (the game's own
colour) used for the primary action and the current step only, sentence case, regular
weight, spacing on a 4 px grid. Colour lives in the maps, not in the chrome.
"""
import sys

# surfaces, darkest first
DEEP = "#12110f"      # sidebar
PAGE = "#161513"      # window background
CARD = "#1c1a18"      # tiles, overlay panels
RAISED = "#262421"    # inputs, selected rows, secondary buttons
# text roles
TEXT = "#efe9de"
TEXT2 = "#aaa398"
MUTED = "#8a847a"
INK = "#12110f"       # text on the accent
# meaning
POS = "#4cc38a"
NEG = "#e5484d"
ROUTE = "#7fd6e0"     # the route line on maps

LIGHT = False

# Alternative ramps, bought with trophy points in the profile window. Same roles, other world.
THEMES = {
    "warm": dict(DEEP="#12110f", PAGE="#161513", CARD="#1c1a18", RAISED="#262421",
                 TEXT="#efe9de", TEXT2="#aaa398", MUTED="#8a847a", POS="#4cc38a", NEG="#e5484d", LIGHT=False),
    "graphite": dict(DEEP="#0f0f10", PAGE="#141415", CARD="#19191b", RAISED="#232325",
                     TEXT="#ededed", TEXT2="#a1a1a6", MUTED="#85858b", POS="#4cc38a", NEG="#e5484d", LIGHT=False),
    "ink": dict(DEEP="#07080d", PAGE="#0b0d14", CARD="#11141c", RAISED="#1a1e28",
                TEXT="#eef0f5", TEXT2="#a3a9b8", MUTED="#7a8296", POS="#4cc38a", NEG="#e5484d", LIGHT=False),
    "paper": dict(DEEP="#f0ebe2", PAGE="#f7f4ee", CARD="#fdfbf7", RAISED="#e6dfd2",
                  TEXT="#1f1b16", TEXT2="#5e554a", MUTED="#7b7266", POS="#16a34a", NEG="#dc2626", LIGHT=True),
}


def apply(name):
    """Switch the ramp. Call before widgets are built: they read the tokens when created."""
    globals().update(THEMES.get(name) or THEMES["warm"])


def accent_text(accent):
    """The accent as a text colour: darkened on a light theme so it stays readable."""
    return mix(accent, "#000000", 0.5) if LIGHT else accent


FONT = "Franklin Gothic Medium" if sys.platform == "win32" else "Helvetica"
MONO = "Consolas" if sys.platform == "win32" else "Courier"

S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 20, 24      # spacing steps


def mix(a, b, t):
    """Colour a moved toward colour b by t (0..1)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(min(255, max(0, int(round(x + (y - x) * t)))) for x, y in zip(ca, cb))


def hair(surface):
    """Hairline on a surface: the primary text colour at 8 %."""
    return mix(surface, TEXT, 0.08)


def init_fonts(root):
    """Pick installed families once a Tk root exists."""
    global FONT, MONO
    try:
        from tkinter import font as tkfont
        fams = set(tkfont.families(root))
    except Exception:
        return
    # Franklin Gothic Medium is the owner's pick (ships with Windows); the rest are fallbacks
    for f in ("Franklin Gothic Medium", "Segoe UI", "Helvetica Neue", "DejaVu Sans", "Helvetica"):
        if f in fams:
            FONT = f
            break
    for f in ("Consolas", "Cascadia Mono", "JetBrains Mono", "Menlo", "DejaVu Sans Mono", "Courier New"):
        if f in fams:
            MONO = f
            break


# -- buttons -----------------------------------------------------------------------
def style_button(b, kind="secondary", accent=None):
    """kind: primary (accent fill), secondary (raised surface), quiet (text only)."""
    parent_bg = b.master.cget("bg")
    if kind == "primary":
        bg, fg = accent or TEXT, INK
        hover, edge = mix(bg, "#ffffff", 0.14), bg
    elif kind == "quiet":
        bg, fg, hover, edge = parent_bg, MUTED, parent_bg, parent_bg
    else:
        bg, fg = RAISED, TEXT
        hover, edge = mix(RAISED, TEXT, 0.07), hair(RAISED)
    b._bg, b._fg, b._hover, b._kind = bg, fg, hover, kind
    b.configure(bg=bg, fg=fg, highlightbackground=edge, highlightcolor=edge)


def button(tk, parent, text, cmd, kind="secondary", accent=None, size=10):
    quiet = kind == "quiet"
    b = tk.Label(parent, text=text, cursor="hand2", font=(FONT, size if not quiet else size - 1),
                 padx=0 if quiet else S4, pady=0 if quiet else 6, highlightthickness=0 if quiet else 1, bd=0)
    style_button(b, kind, accent)
    b.bind("<Enter>", lambda e: b.configure(bg=b._hover, fg=TEXT if b._kind == "quiet" else b._fg))
    b.bind("<Leave>", lambda e: b.configure(bg=b._bg, fg=b._fg))
    b.bind("<Button-1>", lambda e: cmd())
    return b


# -- line icons: one set, one size (16 px box), one stroke ---------------------------
ICONS = {
    "left": [(10, 4, 6, 8, 10, 12)],
    "right": [(6, 4, 10, 8, 6, 12)],
    "check": [(3.5, 8.5, 6.5, 11.5, 12.5, 4.5)],
    "up": [(4, 10, 8, 6, 12, 10)],
    "down": [(4, 6, 8, 10, 12, 6)],
    "close": [(4.5, 4.5, 11.5, 11.5), (11.5, 4.5, 4.5, 11.5)],
    "plus": [(8, 3.5, 8, 12.5), (3.5, 8, 12.5, 8)],
    "minus": [(3.5, 8, 12.5, 8)],
    "menu": [(3.5, 5, 12.5, 5), (3.5, 8, 12.5, 8), (3.5, 11, 12.5, 11)],
}


class IconButton:
    """A 24 px hit area holding a 16 px line icon in the muted text colour."""

    def __init__(self, tk, parent, name, cmd, bg=None):
        bg = self.bg = bg or CARD
        self.c = tk.Canvas(parent, width=24, height=24, bg=bg, highlightthickness=0, cursor="hand2")
        self.name = None
        self.color = MUTED
        self.set(name)
        self.c.bind("<Enter>", lambda e: self._paint(TEXT, RAISED))
        self.c.bind("<Leave>", lambda e: self._paint(MUTED, self.bg))
        self.c.bind("<Button-1>", lambda e: cmd())

    def set(self, name):
        if name != self.name:
            self.name = name
            self._paint(self.color, self.c.cget("bg"))

    def _paint(self, color, bg):
        self.color = color
        self.c.configure(bg=bg)
        self.c.delete("all")
        for pts in ICONS[self.name]:
            self.c.create_line(*[v + 4 for v in pts], fill=color, width=1.5, capstyle="round", joinstyle="round")


def dot(tk, parent, bg, color=None):
    """Small status dot; recolour with canvas.itemconfigure('d', fill=...)."""
    c = tk.Canvas(parent, width=8, height=8, bg=bg, highlightthickness=0)
    c.create_oval(1, 1, 7, 7, fill=color or MUTED, outline="", tags="d")
    return c


class Scroll:
    """Slim scrollbar in the palette (the native one is a bright strip on a dark window)."""

    def __init__(self, tk, parent, target, bg=None):
        self.target, self.lo, self.hi = target, 0.0, 1.0
        self.c = tk.Canvas(parent, width=8, bg=bg or PAGE, highlightthickness=0)
        self.c.bind("<Configure>", lambda e: self._draw())
        self.c.bind("<Button-1>", self._jump)
        self.c.bind("<B1-Motion>", self._jump)

    def set(self, lo, hi):
        self.lo, self.hi = float(lo), float(hi)
        self._draw()

    def _draw(self):
        h = self.c.winfo_height()
        self.c.delete("all")
        if self.hi - self.lo < 0.999:
            self.c.create_rectangle(2, int(h * self.lo), 6, max(int(h * self.hi), int(h * self.lo) + 16),
                                    fill=mix(RAISED, TEXT, 0.12), outline="")

    def _jump(self, e):
        h = max(1, self.c.winfo_height())
        self.target.yview_moveto(max(0.0, e.y / float(h) - (self.hi - self.lo) / 2))
