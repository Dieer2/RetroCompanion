"""The overlay: always on top of the game, the same for every game.

It knows nothing about any particular game. A plugin hands it a view dict (see
GamePlugin.view) and the walkthrough steps; this module lays them out and draws the map.

The overlay is a set of modules, each its own small always-on-top window:

    guide    the step being shown (the anchor: closing it closes the overlay)
    hero     the player's stats
    battle   the enemy, only during a fight
    map      the live map and route
    notes    notes about the current place
    tracker  the achievements closest to completion (an extra bought in the profile shop)
    ach      every achievement of the game, one group at a time, earned or still open
    log      what happened, newest first: enemies beaten, levels, items, steps, achievements

An earned achievement is announced by a pop-up that slides in at the top centre of the screen
(Popup) with the companion's own chime (sound.py), and carries a trophy in its grade's colour
in the achievements module. The map module opens the full-size map (atlas.py).

Resting the pointer on a line that names something the plugin has a tip for (an item, a
weapon, a spell: view()["tips"]) shows what it is in a small window beside the module.

Every module has a compact form (the two chevrons in its header, or C for all of them): no
header, one strip with an icon and the main figures, so the game stays visible. The button
at the end of the strip, or a double-click on it, brings the full module back.

Every module can be collapsed (arrow in its header), resized (drag its right edge for the
width, its bottom edge for the height, the corner for both; text re-wraps, the map rescales
to fit) and moved (drag its header). Height follows the content until it is set by hand;
then longer content is clipped and scrolls with the mouse wheel, and a double-click on the
bottom edge hands the height back to the content. The two list modules (ach, log) start
with a height limit, so a long list scrolls instead of running off the screen. Until a module is moved it is
docked: it sits in a column under the guide and follows it. Moving it tears it off; "Reset
layout" in the right-click menu docks everything again. Layout is saved per game.
"""
import re
import sys
import time
from tkinter import font as tkfont

from . import sound
from . import theme as T
from .atlas import Atlas
from .profile import grade

WIDTH = 380            # default module width
CWIDTH = 280           # default width of a module in its compact form
PAD = T.S3             # inner padding of a module
GAP = T.S2             # space between docked modules
ORDER = ("guide", "hero", "tracker", "battle", "map", "notes", "ach", "log")
TOAST_MS = 7000        # how long an "achievement unlocked" pop-up stays up
TOGGLE = {"hero": "self", "battle": "battle", "map": "map", "notes": "loc", "tracker": "tracker",
          "ach": "ach", "log": "log"}       # module -> show flag
LOG_ROWS = 40          # how many log lines the module shows (the store keeps more)
LIST_H = 300           # height limit of the list modules until the player sets one


class Ctx:
    """What a plugin gets alongside the state when asked for a view."""

    def __init__(self, step, index, zoom, current=None, done=(), seen=()):
        self.step = step            # the step being shown
        self.index = index
        self.zoom = zoom
        self.current = index if current is None else current    # the step the player is on
        self.done = done            # ids of the finished steps
        self.seen = seen            # what the plugin's observe() recorded


def R(kind, value, gap=T.S1, act=None):
    """One row of a module: kind is a text style, or 'bar' / 'map'."""
    return (kind, value, gap, act)


class MapView:
    """Draws a map spec:
         base     hashable id of the tile grid (cached as an image)
         rows     list of strings, one character per tile
         palette  {character: color}
         x0, y0, vw, vh   visible window in tiles
         z        pixels per tile at the default module width (scaled to the real width)
         rects    [(x, y, color)]      tiles to repaint (opened chests, bridges...)
         labels   [(x, y, text)]       small text on tiles
         path     [(x, y)]             route polyline
         goal     (x, y) or None       ringed target
         player   (x, y)
    """

    def __init__(self, tk, parent):
        self.tk = tk
        self.canvas = tk.Canvas(parent, width=10, height=10, bg=T.CARD, highlightthickness=0)
        self.base = {}
        self.img = None
        self.key = None

    def _base(self, spec):
        if spec["base"] not in self.base:
            rows, pal = spec["rows"], spec["palette"]
            img = self.tk.PhotoImage(width=len(rows[0]), height=len(rows))
            img.put(" ".join("{" + " ".join(pal.get(c, "#000000") for c in row) + "}" for row in rows))
            self.base[spec["base"]] = img
        return self.base[spec["base"]]

    @staticmethod
    def sig(spec):
        return (spec["base"], spec["x0"], spec["y0"], spec["vw"], spec["vh"], spec["z"],
                tuple(spec.get("rects", ())), tuple(spec.get("labels", ())), tuple(spec.get("path", ())),
                spec.get("goal"), spec.get("player"))

    def draw(self, spec, avail, maxh=None):
        z = max(1, int(spec["z"] * avail / float(WIDTH - 2 * PAD - 2)))
        if maxh is not None:                # a module with a set height: the whole map must fit in it
            z = max(1, min(z, maxh // spec["vh"]))
        key = (self.sig(spec), z)
        if key == self.key:
            return
        self.key = key
        x0, y0, vw, vh = spec["x0"], spec["y0"], spec["vw"], spec["vh"]
        c = self.canvas
        img = self.tk.PhotoImage()
        img.tk.call(img, "copy", self._base(spec), "-from", x0, y0, x0 + vw, y0 + vh, "-zoom", z, z)
        self.img = img
        c.configure(width=vw * z, height=vh * z)
        c.delete("all")
        c.create_image(0, 0, image=img, anchor="nw")

        def pos(x, y):
            return (x - x0) * z + z / 2.0, (y - y0) * z + z / 2.0

        def vis(x, y):
            return x0 <= x < x0 + vw and y0 <= y < y0 + vh

        for x, y, color in spec.get("rects", ()):
            if vis(x, y):
                px, py = pos(x, y)
                c.create_rectangle(px - z / 2, py - z / 2, px + z / 2, py + z / 2, fill=color, outline="")
        for x, y, text in spec.get("labels", ()):
            if vis(x, y) and z >= 9:
                px, py = pos(x, y)
                c.create_text(px, py, text=text, fill="#000000", font=(T.MONO, max(6, z - 4)))
        pts = [p for p in spec.get("path", ()) if vis(*p)]
        if len(pts) >= 2:
            flat = []
            for x, y in pts:
                flat.extend(pos(x, y))
            c.create_line(*flat, fill=T.ROUTE, width=max(2, z // 4), capstyle="round", joinstyle="round")
        goal = spec.get("goal")
        if goal and vis(*goal):
            px, py = pos(*goal)
            r = max(4, z * 0.7)
            c.create_oval(px - r, py - r, px + r, py + r, outline=T.ROUTE, width=2)
        pl = spec.get("player")
        if pl and vis(*pl):
            px, py = pos(*pl)
            r = max(3, z * 0.45)
            c.create_rectangle(px - r, py - r, px + r, py + r, fill="#ffffff", outline=T.NEG, width=2)


class Panel:
    """One module window: header (drag to move), body rows, right edge (drag to resize)."""
    MINW, MAXW, MINH, CMINW = 240, 720, 72, 170

    def __init__(self, ov, name, tools=(), with_dot=False, limit=None):
        tk = self.tk = ov.tk
        self.ov, self.name = ov, name
        self.limit = limit          # a height the content may grow to before it scrolls (None: no limit)
        self.cfg = ov.ui.setdefault("panels", {}).setdefault(name, {})
        self.compact = bool(self.cfg.get("compact", False))
        self.w = self.width()
        self.collapsed = bool(self.cfg.get("collapsed", False))
        self.shown = False
        self._key = self._geom = None
        self._labels = []
        self._irows = []

        win = self.win = tk.Toplevel(ov.master)
        win.withdraw()
        win.title("%s: %s" % (ov.p.title, name))
        win.configure(bg=T.hair(T.CARD))
        if sys.platform != "darwin":
            win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self.close)
        outer = self.outer = tk.Frame(win, bg=T.CARD)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        head = self.head = tk.Frame(outer, bg=T.CARD)
        head.pack(fill="x")
        self.dot = None
        if with_dot:
            self.dot = T.dot(tk, head, T.CARD)
            self.dot.pack(side="left", padx=(PAD, 0))
        self.title = tk.Label(head, text="", bg=T.CARD, fg=T.TEXT2, anchor="w")
        self.title.pack(side="left", fill="x", expand=True, padx=(T.S2 if with_dot else PAD, T.S1))
        T.IconButton(tk, head, "close", self.close).c.pack(side="right", padx=(0, T.S2), pady=T.S1)
        self.fold = T.IconButton(tk, head, "up", self.toggle_collapse)
        self.fold.c.pack(side="right", pady=T.S1)
        T.IconButton(tk, head, "compact", self.toggle_compact).c.pack(side="right", pady=T.S1)
        self.tools = {}
        for icon, act in reversed(tools):
            self.tools[act] = T.IconButton(tk, head, icon, lambda a=act: ov.action(a))
            self.tools[act].c.pack(side="right", pady=T.S1)
        self.sep = tk.Frame(outer, bg=T.hair(T.CARD), height=1)
        # the body sits in a canvas so a module with a set height can clip and scroll it
        self.view = tk.Canvas(outer, bg=T.CARD, highlightthickness=0, yscrollincrement=16)
        self.body = tk.Frame(self.view, bg=T.CARD)
        self.view.create_window(0, 0, window=self.body, anchor="nw", tags="b")
        self.bar = tk.Canvas(self.body, height=6, bg=T.RAISED, highlightthickness=0)
        self.mapv = MapView(tk, self.body)
        # the compact form: no header, one strip (icon, the main figures, a button back to full size)
        self.strip = tk.Frame(self.body, bg=T.CARD)
        self.sicon = tk.Canvas(self.strip, width=20, height=20, bg=T.CARD, highlightthickness=0)
        self.sicon.pack(side="left", anchor="n", pady=2)
        T.IconButton(tk, self.strip, "expand", self.toggle_compact).c.pack(side="right", anchor="n")
        self.stext = tk.Label(self.strip, bg=T.CARD, fg=T.TEXT, justify="left", anchor="w")
        self.stext.pack(side="left", fill="x", expand=True, padx=(T.S2, 0), pady=2)
        self._hover(self.stext)
        self._hover(self.title)
        self.h = self.body_h = self.view_h = 0

        # resize handles: right edge = width, bottom edge = height, corner = both
        for mode, cursor, where in (
                ("w", "sb_h_double_arrow", dict(relx=1.0, x=-1, y=1, anchor="ne", relheight=1.0, height=-2, width=5)),
                ("h", "sb_v_double_arrow", dict(rely=1.0, y=-1, x=1, anchor="sw", relwidth=1.0, width=-2, height=5)),
                ("wh", "size_nw_se", dict(relx=1.0, rely=1.0, x=-1, y=-1, anchor="se", width=12, height=12))):
            edge = tk.Frame(win, bg=T.CARD, cursor=cursor)
            edge.place(**where)
            edge.bind("<Enter>", lambda e, w=edge: w.configure(bg=T.RAISED))
            edge.bind("<Leave>", lambda e, w=edge: w.configure(bg=T.CARD))
            edge.bind("<ButtonPress-1>", lambda e, m=mode: self.size_start(e, m))
            edge.bind("<B1-Motion>", self.size_move)
            edge.bind("<ButtonRelease-1>", self.size_end)
            if "h" in mode:
                edge.bind("<Double-Button-1>", self.auto_height)
        win.bind("<MouseWheel>", lambda e: self.scroll(-1 if e.delta > 0 else 1))
        win.bind("<Button-4>", lambda e: self.scroll(-1))
        win.bind("<Button-5>", lambda e: self.scroll(1))
        for w in (head, self.title, self.strip, self.sicon, self.stext) + ((self.dot,) if self.dot else ()):
            w.bind("<ButtonPress-1>", self.drag_start)
            w.bind("<B1-Motion>", self.drag_move)
            w.bind("<ButtonRelease-1>", self.drag_end)
        for w in (self.strip, self.sicon, self.stext):
            w.bind("<Double-Button-1>", lambda e: self.toggle_compact())
        win.bind("<Button-3>", lambda e: ov.menu.tk_popup(e.x_root, e.y_root))
        for key, act in (("<Right>", "next"), ("<Left>", "prev"), ("d", "done"), ("h", "hide"), ("a", "auto"),
                         ("l", "loc"), ("m", "map"), ("s", "self"), ("z", "zoom"), ("c", "compact"), ("f", "atlas"),
                         ("<Escape>", "auto")):
            win.bind(key, lambda e, a=act: ov.action(a))

    # -- state -----------------------------------------------------------------
    @property
    def free(self):
        """Torn off: placed by the user instead of docked under the guide."""
        return "x" in self.cfg

    def close(self):
        self.ov.action("quit" if self.name == "guide" else TOGGLE[self.name])

    def width(self):
        """Full size and compact keep their own widths."""
        key, default, low = ("cw", CWIDTH, self.CMINW) if self.compact else ("w", WIDTH, self.MINW)
        return max(low, min(self.MAXW, int(self.cfg.get(key, default))))

    def set_compact(self, value):
        self.compact = self.cfg["compact"] = bool(value)
        self.w = self.width()
        self.ov.save_ui()

    def toggle_compact(self):
        self.set_compact(not self.compact)
        self.ov.render(force=True)

    def toggle_collapse(self):
        self.set_collapsed(not self.collapsed)
        self.ov.render(force=True)

    def set_collapsed(self, value):
        self.collapsed = self.cfg["collapsed"] = bool(value)
        self.ov.save_ui()

    # -- moving ----------------------------------------------------------------
    def drag_start(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def drag_move(self, e):
        x, y = e.x_root - self._drag[0], e.y_root - self._drag[1]
        if self.name == "guide":
            self.ov.ui["pos"] = [x, y]
        else:
            self.cfg["x"], self.cfg["y"] = x, y
        self.ov.layout()

    def drag_end(self, e):
        self.ov.save_ui()

    # -- resizing --------------------------------------------------------------
    def size_start(self, e, mode="w"):
        self._size = (mode, e.x_root, e.y_root, self.w, self.h)

    def size_move(self, e):
        mode, x0, y0, w0, h0 = self._size
        changed = False
        if "w" in mode:
            w = max(self.CMINW if self.compact else self.MINW, min(self.MAXW, w0 + e.x_root - x0))
            if w != self.w:
                self.w = self.cfg["cw" if self.compact else "w"] = w
                changed = True
        if "h" in mode and not self.collapsed and not self.compact:
            h = max(self.MINH, min(self.win.winfo_screenheight(), h0 + e.y_root - y0))
            if h != self.cfg.get("h"):
                self.cfg["h"] = h
                changed = True
        if changed:
            self.ov.render(force=True)

    def size_end(self, e):
        self.ov.save_ui()

    def auto_height(self, e=None):
        """Back to a height that follows the content (double-click the bottom edge)."""
        if self.cfg.pop("h", None) is not None:
            if self.limit:
                self.cfg["h"] = 0           # 0 = follow the content, without the starting limit
            self.ov.save_ui()
            self.ov.render(force=True)

    def scroll(self, units):
        if self.body_h > self.view_h and not self.collapsed:
            self.view.yview_scroll(units * 2, "units")

    # -- content ---------------------------------------------------------------
    def _label(self, i):
        while len(self._labels) <= i:
            lbl = self.tk.Label(self.body, bg=T.CARD, justify="left", anchor="w")
            lbl._act = None
            lbl.bind("<Button-1>", lambda e, l=lbl: l._act and self.ov.action(l._act))
            self._hover(lbl)
            self._labels.append(lbl)
        return self._labels[i]

    def _irow(self, i):
        """A text row with room for a 16 px line icon in front of it."""
        while len(self._irows) <= i:
            f = self.tk.Frame(self.body, bg=T.CARD)
            c = self.tk.Canvas(f, width=16, height=16, bg=T.CARD, highlightthickness=0)
            c.pack(side="left", anchor="n", pady=1)
            lbl = self.tk.Label(f, bg=T.CARD, justify="left", anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=(T.S2, 0))
            self._hover(lbl)
            self._irows.append((f, c, lbl))
        return self._irows[i]

    def _hover(self, lbl):
        """The pointer on a line shows what the things named in it are."""
        lbl.bind("<Enter>", lambda e, l=lbl: self.ov.tip_show(self, l, e), add="+")
        lbl.bind("<Motion>", lambda e, l=lbl: self.ov.tip_show(self, l, e), add="+")
        lbl.bind("<Leave>", lambda e: self.ov.tip_hide(), add="+")

    def set(self, title, rows, dot=None, short=None):
        """rows: [R(...)]; an empty list hides the module. A row of kind "irow" has the value
        (icon or None, tint, text style, text): the icon sits in a column of its own. short = (icon, text, rows, tint) is the
        compact form: one strip with an icon and the main figures, then at most a row or two."""
        if not rows:
            self.hide()
            return
        ov = self.ov
        small = self.compact and short is not None
        if small:
            icon, text, rows, tint = short
        sig = tuple((k, MapView.sig(v) if k == "map" else v, g, a) for k, v, g, a in rows)
        fixed = None if small else (self.cfg.get("h") or None)
        cap = None if small or "h" in self.cfg else self.limit     # no height chosen yet: the content up to the limit
        key = (title, sig, dot, self.w, fixed, self.collapsed, ov.fsize, (icon, text, tint) if small else None)
        if key != self._key:
            self._key = key
            n = ov.fsize
            styles = {"meta": (T.MUTED, (T.FONT, n - 1)), "body": (T.TEXT2, (T.FONT, n)),
                      "strong": (T.TEXT, (T.FONT, n)), "title": (T.TEXT, (T.FONT, n + 3)),
                      "mono": (T.TEXT, (T.MONO, n)), "warn": (T.NEG, (T.FONT, n)),
                      "link": (T.MUTED, (T.FONT, n - 1, "underline"))}
            for wdg in self.body.winfo_children():
                wdg.pack_forget()
            self.head.pack_forget()
            self.sep.pack_forget()
            self.view.pack_forget()
            if small:
                head_h, chrome = 0, 2 + 2 * T.S1
            else:
                self.title.configure(text=title, font=(T.FONT, n))
                if self.dot is not None and dot:
                    self.dot.itemconfigure("d", fill=dot)
                self.fold.set("down" if self.collapsed else "up")
                self.head.pack(fill="x")
                self.win.update_idletasks()
                head_h = self.head.winfo_reqheight()
                chrome = 2 + head_h + 1 + T.S2 + PAD            # everything in the window except the body
            self.h = 2 + head_h
            if small or not self.collapsed:
                wrap = self.w - 2 - 2 * PAD
                room = None if fixed is None else max(0, fixed - chrome)
                used = iused = 0
                if small:
                    self.sicon.delete("all")
                    for pts in T.ICONS[icon]:
                        self.sicon.create_line(*[v + 2 for v in pts], fill=tint or T.MUTED, width=1.5,
                                               capstyle="round", joinstyle="round")
                    self.stext.configure(text=text, font=(T.FONT, n),
                                         wraplength=max(60, self.w - 2 - T.S2 - 20 - T.S2 - 24 - T.S1))
                    self.strip.pack(fill="x", padx=(T.S2, T.S1))
                for i, (kind, value, gap, act) in enumerate(rows):
                    top = gap if (i or small) else 0
                    if kind == "map":
                        self.mapv.draw(value, wrap, None if room is None else room - top)
                        self.mapv.canvas.pack(pady=(top, 0))
                    elif kind == "bar":
                        self.bar.configure(width=wrap)
                        self.bar.delete("all")
                        self.bar.create_rectangle(0, 0, int(wrap * max(0.0, min(1.0, value))), 6, fill=T.TEXT2, outline="")
                        self.bar.pack(padx=PAD, pady=(top, 0), anchor="w")
                    elif kind == "irow":
                        icon, tint, style, text = value
                        f, c, lbl = self._irow(iused)
                        iused += 1
                        c.delete("all")
                        for pts in T.ICONS[icon] if icon else ():
                            c.create_line(*pts, fill=tint or T.MUTED, width=1.5, capstyle="round", joinstyle="round")
                        fg, font = styles[style]
                        lbl.configure(text=text, fg=fg, font=font, wraplength=wrap - 16 - T.S2)
                        f.pack(fill="x", padx=PAD, pady=(top, 0))
                    else:
                        lbl = self._label(used)
                        used += 1
                        fg, font = styles[kind]
                        lbl._act = act
                        lbl.configure(text=value, fg=fg, font=font, wraplength=wrap, cursor="hand2" if act else "")
                        lbl.pack(fill="x", padx=PAD, pady=(top, 0))
                self.body.update_idletasks()
                bw = self.w - 2
                self.body_h = self.body.winfo_reqheight()
                self.view_h = self.body_h if room is None else room      # set height: clip, wheel scrolls
                if cap and room is None:
                    self.view_h = min(self.body_h, max(0, cap - chrome))
                self.view.itemconfigure("b", width=bw)
                self.view.configure(width=bw, height=self.view_h,
                                    scrollregion=(0, 0, bw, max(self.body_h, self.view_h)))
                if self.body_h <= self.view_h:
                    self.view.yview_moveto(0)
                if small:
                    self.view.pack(fill="x", pady=(T.S1, T.S1 + (T.S2 if rows else 0)))
                    chrome += T.S2 if rows else 0
                else:
                    self.sep.pack(fill="x")
                    self.view.pack(fill="x", pady=(T.S2, PAD))
                self.h = chrome + self.view_h
        self.shown = True

    def hide(self):
        if self.shown or self._geom is not None:
            self.win.withdraw()
        self.shown, self._geom = False, None

    def place(self, x, y):
        geom = "%dx%d+%d+%d" % (self.w, self.h, x, y)
        if geom != self._geom:
            first = self._geom is None
            self._geom = geom
            self.win.geometry(geom)
            if first:
                self.win.deiconify()
                self.win.attributes("-topmost", True)


class Popup:
    """"Achievement unlocked", the way consoles announce it: a card that slides in at the top
    centre of the screen, stays a few seconds and slides out. A click sends it away."""
    W, TOP, MS = 440, 24, 280

    def __init__(self, ov):
        tk = self.tk = ov.tk
        self.ov = ov
        self.up = False
        self._job = None
        self.h = 0
        win = self.win = tk.Toplevel(ov.master)
        win.withdraw()
        win.title("%s: achievement" % ov.p.title)
        win.configure(bg=T.hair(T.CARD))
        if sys.platform != "darwin":
            win.overrideredirect(True)
        win.attributes("-topmost", True)
        box = self.box = tk.Frame(win, bg=T.CARD)
        box.pack(fill="both", expand=True, padx=1, pady=1)
        self.icon = tk.Canvas(box, width=56, height=56, bg=T.CARD, highlightthickness=0)
        self.icon.pack(side="left", padx=(T.S4, 0), pady=T.S4, anchor="n")
        col = self.col = tk.Frame(box, bg=T.CARD)
        col.pack(side="left", fill="both", expand=True, padx=T.S4, pady=T.S4)
        self.meta = tk.Label(col, bg=T.CARD, fg=T.MUTED, anchor="w", justify="left")
        self.name = tk.Label(col, bg=T.CARD, fg=T.TEXT, anchor="w", justify="left")
        self.text = tk.Label(col, bg=T.CARD, fg=T.TEXT2, anchor="w", justify="left")
        self.pts = tk.Label(col, bg=T.CARD, fg=T.TEXT, anchor="w", justify="left")
        self.meta.pack(fill="x")
        self.name.pack(fill="x", pady=(2, 0))
        self.text.pack(fill="x", pady=(T.S1, 0))
        self.pts.pack(fill="x", pady=(T.S2, 0))
        for w in (win, box, col, self.icon, self.meta, self.name, self.text, self.pts):
            w.bind("<Button-1>", lambda e: ov.action("toast_next"))

    def show(self, a, count, total, style="card"):
        """style: card (the standard one), banner (one slim line) or edge (the grade's colour around it)."""
        n, wrap = self.ov.fsize, self.W - 2 - 56 - 3 * T.S4
        g = grade(a["points"])
        tint = T.TROPHY[g]
        c = self.icon
        c.delete("all")
        slim = style == "banner"
        k = 0.57 if slim else 1.0                       # the banner's badge is 32 px
        c.configure(width=int(56 * k), height=int(56 * k))
        c.pack_configure(pady=T.S2 if slim else T.S4)
        c.create_oval(2, 2, 56 * k - 2, 56 * k - 2, outline=tint, width=2, fill=tint if style == "edge" else "")
        for pts in T.ICONS["trophy"]:
            c.create_line(*[(v * 2.4 + 8.8) * k for v in pts], fill=T.INK if style == "edge" else tint,
                          width=2.5 if not slim else 1.5, capstyle="round", joinstyle="round")
        self.win.configure(bg=tint if style == "edge" else T.hair(T.CARD))
        self.box.pack_configure(padx=2 if style == "edge" else 1, pady=2 if style == "edge" else 1)
        self.col.pack_configure(pady=T.S2 if slim else T.S4)
        for w in (self.meta, self.name, self.text, self.pts):
            w.pack_forget()
        points = "+%d points · %s   %d / %d" % (a["points"], g, count, total)
        if slim:
            self.name.configure(text=a["title"], font=(T.FONT, n + 1), wraplength=0)
            self.pts.configure(text=points, font=(T.MONO, n - 1))
            self.pts.pack(side="right")
            self.name.pack(side="left", fill="x", expand=True)
        else:
            self.meta.configure(text="Achievement unlocked", font=(T.FONT, n - 1))
            self.name.configure(text=a["title"], font=(T.FONT, n + 4), wraplength=wrap)
            self.text.configure(text=a["text"], font=(T.FONT, n), wraplength=wrap)
            self.pts.configure(text=points, font=(T.MONO, n))
            self.meta.pack(fill="x")
            self.name.pack(fill="x", pady=(2, 0))
            self.text.pack(fill="x", pady=(T.S1, 0))
            self.pts.pack(fill="x", pady=(T.S2, 0))
        self.win.update_idletasks()
        self.h = self.win.winfo_reqheight()
        self.x = (self.win.winfo_screenwidth() - self.W) // 2
        try:
            self.win.attributes("-alpha", max(0.9, self.ov.alpha))
        except self.tk.TclError:
            pass
        if not self.up:                     # already on screen: the next one takes its place
            self.up = True
            self._move(-self.h)
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self._slide(-self.h, self.TOP, None)
        else:
            self._move(self.TOP)

    def hide(self):
        if self.up:
            self.up = False
            self._slide(self.TOP, -self.h, self.win.withdraw)

    def _move(self, y):
        self.win.geometry("%dx%d+%d+%d" % (self.W, self.h, self.x, int(y)))

    def _slide(self, y0, y1, then, t0=None):
        if self._job is not None:
            self.win.after_cancel(self._job)
            self._job = None
        now = time.time()
        t0 = t0 or now
        k = min(1.0, (now - t0) * 1000.0 / self.MS)
        self._move(y0 + (y1 - y0) * (1 - (1 - k) ** 3))        # one ease-out curve, in and out
        if k < 1.0:
            self._job = self.win.after(16, lambda: self._slide(y0, y1, then, t0))
        elif then:
            then()

    def destroy(self):
        if self._job is not None:
            self.win.after_cancel(self._job)
        try:
            self.win.destroy()
        except self.tk.TclError:
            pass


class Tip:
    """What a named thing is: a small window beside the module the pointer is on."""
    W = 300

    def __init__(self, ov):
        tk = self.tk = ov.tk
        self.ov = ov
        self.key = None
        win = self.win = tk.Toplevel(ov.master)
        win.withdraw()
        win.configure(bg=T.hair(T.RAISED))
        if sys.platform != "darwin":
            win.overrideredirect(True)
        win.attributes("-topmost", True)
        self.box = tk.Frame(win, bg=T.RAISED)
        self.box.pack(fill="both", expand=True, padx=1, pady=1)
        self.labels = []

    def show(self, items, panel, y):
        """items: [(name, lines)]."""
        key = (tuple((n, tuple(ls)) for n, ls in items), panel.name)
        if key != self.key:
            self.key = key
            n, wrap, used = self.ov.fsize, self.W - 2 - 2 * T.S3, 0
            for lbl in self.labels:
                lbl.pack_forget()
            rows = []
            for i, (name, lines) in enumerate(items):
                rows.append((name, T.TEXT, (T.FONT, n), T.S3 if i else 0))
                rows += [(ln, T.TEXT2, (T.FONT, n - 1), 2) for ln in lines]
            for k, (text, fg, font, top) in enumerate(rows):
                if used == len(self.labels):
                    self.labels.append(self.tk.Label(self.box, bg=T.RAISED, anchor="w", justify="left"))
                lbl = self.labels[used]
                used += 1
                lbl.configure(text=text, fg=fg, font=font, wraplength=wrap)
                lbl.pack(fill="x", padx=T.S3, pady=(top if k else T.S2, T.S2 if k == len(rows) - 1 else 0))
            self.win.update_idletasks()
        h = self.win.winfo_reqheight()
        px, pw = panel.win.winfo_rootx(), panel.win.winfo_width()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        x = px + pw + T.S1 if px + pw + T.S1 + self.W <= sw else px - T.S1 - self.W      # beside the module, never over it
        self.win.geometry("%dx%d+%d+%d" % (self.W, h, max(0, x), max(0, min(y - 12, sh - h - 48))))
        self.win.deiconify()
        self.win.attributes("-topmost", True)

    def hide(self):
        self.win.withdraw()

    def destroy(self):
        try:
            self.win.destroy()
        except self.tk.TclError:
            pass


class Overlay:
    def __init__(self, tk, master, plugin, progress, ui, save_ui, on_close, ach=None, modules=(), log=None,
                 look=None):
        self.tk = tk
        self.look = look or (lambda: {})    # the player's choices from the shop: {"chime": id, "popup": id}
        self.master = master
        self.ach = ach              # the game's Achievements, for the tracker and the list
        self.log = log if log is not None else []      # [[unix time, text]], oldest first; the dashboard appends
        self.ach_page = 0           # which group the achievements module shows
        self.modules = set(modules) # extra modules the player owns and has switched on
        self.p = plugin
        self.progress = progress
        self.ui = ui
        self.save_ui = save_ui
        self.on_close = on_close
        self.state = None
        self.conn = "offline"       # live | nostate | nocore | offline
        self.conn_msg = ""
        self.view = None            # None = follow progress automatically
        self.show = {k: ui.get(k, True) for k in ("loc", "map", "self", "zoom", "battle", "tracker", "ach", "log")}
        self.alpha = float(ui.get("alpha", 0.92))
        self.fsize = int(ui.get("fsize", 10))
        self.closed = False
        self.toasts = []            # achievements waiting to be shown; the first one is on screen
        self._toast_timer = None
        self.popup = Popup(self)
        self.info = []              # lines the library adds to the stats module (play time, last save)
        self.tips, self._tip_re, self._tip_names = {}, None, None       # what the plugin can explain
        self._fonts = {}            # font description -> Font, for finding the word under the pointer
        self.tipwin = Tip(self)
        self.atlas = None           # the full-size map window, while it is open

        m = self.menu = tk.Menu(master, tearoff=0)
        for label, act in (("Next step  (Right)", "next"), ("Previous step  (Left)", "prev"),
                           ("Back to the current step  (A)", "auto"), ("Mark step done / skip  (D)", "done")):
            m.add_command(label=label, command=lambda a=act: self.action(a))
        m.add_separator()
        for label, act in (("Map  (M)", "map"), ("Map zoom  (Z)", "zoom"), ("Full-size map  (F)", "atlas"),
                           ("My stats  (S)", "self"),
                           ("Location notes  (L)", "loc"), ("Battle module", "battle"),
                           ("Achievements", "ach"), ("Event log", "log")) + (
                           (("Trophy tracker", "tracker"),) if "tracker" in self.modules else ()) + (
                           ("Compact / full size, all  (C)", "compact"), ("Collapse / expand all  (H)", "hide"),
                           ("Reset layout", "reset")):
            m.add_command(label=label, command=lambda a=act: self.action(a))
        m.add_separator()
        m.add_command(label="Bigger text", command=lambda: self.set_font(+1))
        m.add_command(label="Smaller text", command=lambda: self.set_font(-1))
        m.add_command(label="More transparent", command=lambda: self.set_alpha(-0.1))
        m.add_command(label="Less transparent", command=lambda: self.set_alpha(+0.1))
        m.add_command(label="Achievement sound on / off", command=lambda: self.action("sound"))
        m.add_separator()
        if sys.platform == "win32":
            m.add_command(label="In RetroArch the keys work with Ctrl+Shift held", state="disabled")
        m.add_command(label="Close overlay", command=lambda: self.action("quit"))

        self.panels = {
            "guide": Panel(self, "guide", with_dot=True,
                           tools=(("left", "prev"), ("right", "next"), ("check", "done"))),
            "hero": Panel(self, "hero"),
            "tracker": Panel(self, "tracker"),
            "battle": Panel(self, "battle"),
            "map": Panel(self, "map", tools=(("full", "atlas"), ("minus", "zoom"))),
            "notes": Panel(self, "notes"),
            "ach": Panel(self, "ach", tools=(("left", "ach_prev"), ("right", "ach_next")), limit=LIST_H),
            "log": Panel(self, "log", limit=LIST_H),
        }
        self.set_alpha(0)
        self.render()

    # -- settings ------------------------------------------------------------
    def set_font(self, d):
        self.fsize = max(8, min(18, self.fsize + d))
        self.ui["fsize"] = self.fsize
        self.save_ui()
        self.render(force=True)

    def set_alpha(self, d):
        self.alpha = max(0.35, min(1.0, self.alpha + d))
        if d:
            self.ui["alpha"] = self.alpha
            self.save_ui()
        for p in self.panels.values():
            try:
                p.win.attributes("-alpha", self.alpha)
            except self.tk.TclError:
                pass

    # -- achievements ----------------------------------------------------------
    def toast(self, ach, count, total):
        """Announce an earned achievement: pop-up and chime; several queue up one after another."""
        self.toasts.append((ach, count, total))
        groups = self._groups()
        if ach.get("group", "") in groups:              # the achievements module turns to its group
            self.ach_page = groups.index(ach.get("group", ""))
        if len(self.toasts) == 1:
            self._announce()
        self.render(force=True)

    def _announce(self):
        look = self.look()
        self.popup.show(*self.toasts[0], style=look.get("popup", "card"))
        if self.ui.get("sound", True):
            sound.play(look.get("chime", "trophy"))
        self._toast_timer = self.master.after(TOAST_MS, lambda: self.action("toast_next"))

    def char_at(self, lbl, x, y):
        """Index into a label's text of the character under a point of it (the label wraps at spaces)."""
        key = str(lbl.cget("font"))
        f = self._fonts.get(key)
        if f is None:
            f = self._fonts[key] = tkfont.Font(root=self.master, font=lbl.cget("font"))
        text = lbl.cget("text")
        wrap = int(lbl.cget("wraplength")) or 10 ** 6
        lines, pos = [], 0
        for para in text.split("\n"):
            start, cur = pos, ""
            for word in re.split(r"(\s+)", para):
                if cur.strip() and word.strip() and f.measure(cur + word) > wrap:
                    lines.append((start, cur))
                    start, cur = start + len(cur), word
                else:
                    cur += word
            lines.append((start, cur))
            pos += len(para) + 1
        start, s = lines[max(0, min(len(lines) - 1, (y - 2) // max(1, f.metrics("linespace"))))]
        for i in range(1, len(s) + 1):
            if f.measure(s[:i]) >= x:
                return start + i - 1
        return start + len(s)

    def tip_show(self, panel, lbl, e):
        """Show what the thing under the pointer is (one of the names the plugin gave tips for)."""
        text = lbl.cget("text")
        if not self.tips or not text:
            return
        names = tuple(sorted(self.tips, key=len, reverse=True))
        if names != self._tip_names:            # longest first, whole words only: "Herb" is not in "Herbs"
            self._tip_names = names
            self._tip_re = re.compile(r"(?<![A-Za-z])(%s)(?![A-Za-z])" % "|".join(re.escape(n) for n in names))
        found = [(m.start(), m.end(), m.group(1)) for m in self._tip_re.finditer(text) if self.tips[m.group(1)]]
        if not found:
            self.tipwin.hide()
            return
        at = self.char_at(lbl, e.x, e.y)        # the name under the pointer, else the nearest one in the line
        name = min(found, key=lambda m: 0 if m[0] <= at < m[1] else min(abs(at - m[0]), abs(at - m[1])))[2]
        lines = list(self.tips[name])
        others = len({m[2] for m in found}) - 1
        if others:
            lines.append("This line names %d more: move along it" % others)
        self.tipwin.show([(name, lines)], panel, lbl.winfo_rooty())

    def tip_hide(self):
        self.tipwin.hide()

    def _groups(self):
        groups = []
        for a in (self.ach.items if self.ach is not None else ()):
            if a.get("group", "") not in groups:
                groups.append(a.get("group", ""))
        return groups

    def ctx(self, idx=None):
        """What the plugin gets with the state: the step shown and where the walkthrough stands."""
        pr, steps = self.progress, self.p.steps
        cur = pr.current()
        idx = (cur if self.view is None else self.view) if idx is None else idx
        return Ctx(steps[idx], idx, self.show["zoom"], cur,
                   frozenset(s["id"] for i, s in enumerate(steps) if pr.is_done(i)), frozenset(pr.seen))

    # -- events --------------------------------------------------------------
    def action(self, a):
        if self.closed:
            return
        if a == "toast_next":
            if self._toast_timer is not None:
                self.master.after_cancel(self._toast_timer)
                self._toast_timer = None
            del self.toasts[:1]
            if self.toasts:
                self._announce()
            else:
                self.popup.hide()
            return
        if a == "sound":
            self.ui["sound"] = not self.ui.get("sound", True)
            self.save_ui()
            if self.ui["sound"]:
                sound.play(self.look().get("chime", "trophy"))
            return
        if a == "atlas":
            if self.atlas is not None:
                self.atlas.close()
            else:
                data = self.p.atlas(self.state if self.conn == "live" else None, self.ctx())
                if data:
                    self.atlas = Atlas(self, data)
            return
        steps = self.p.steps
        shown = self.progress.current() if self.view is None else self.view
        if a == "quit":
            self.close()
            self.on_close()
            return
        if a == "next":
            self.view = min(len(steps) - 1, shown + 1)
        elif a == "prev":
            self.view = max(0, shown - 1)
        elif a == "auto":
            self.view = None
        elif a in ("ach_prev", "ach_next"):
            self.ach_page += 1 if a == "ach_next" else -1
            self.panels["ach"].view.yview_moveto(0)
        elif a == "done":
            self.progress.toggle(shown)
            self.view = None
        elif a == "compact":                # all compact, or all back to full size
            live = [p for p in self.panels.values() if p.shown]
            small = any(not p.compact for p in live)
            for p in self.panels.values():
                p.set_compact(small)
        elif a == "hide":
            live = [p for p in self.panels.values() if p.shown]
            fold = any(not p.collapsed for p in live)
            for p in live:
                p.set_collapsed(fold)
        elif a == "reset":
            for p in self.panels.values():
                p.cfg.clear()
                p.w, p.collapsed, p.compact = WIDTH, False, False
            self.save_ui()
        elif a in self.show:
            self.show[a] = not self.show[a]
            self.ui[a] = self.show[a]
            self.save_ui()
        self.render(force=True)

    def close(self):
        self.closed = True
        if self._toast_timer is not None:
            self.master.after_cancel(self._toast_timer)
        self.popup.destroy()
        self.tipwin.destroy()
        if self.atlas is not None:
            self.atlas.close()
        for p in self.panels.values():
            try:
                p.win.destroy()
            except self.tk.TclError:
                pass

    def set_info(self, lines):
        """Lines from the library for the stats module; redraws only when they change."""
        if list(lines) != self.info:
            self.info = list(lines)
            self.render()

    def update(self, conn, state, msg=""):
        self.conn, self.state, self.conn_msg = conn, state, msg
        self.render()

    # -- drawing -------------------------------------------------------------
    def render(self, force=False):
        if self.closed:
            return
        p, P = self.p, self.panels
        if force:
            for pan in P.values():
                pan._key = None
        g = self.state if self.conn == "live" else None
        ctx = self.ctx()
        idx, step = ctx.index, ctx.step
        pv = p.view(g, ctx) or {}
        self.tips = pv.get("tips") or {}

        rows = []
        if g is not None:
            dot = T.POS
        elif self.conn == "nostate":
            dot = T.MUTED
            rows.append(R("meta", "Connected. Load a save or start a game"))
        elif self.conn == "nocore":
            dot = T.MUTED
            rows.append(R("meta", "RetroArch answers but sends no memory data (%s). Try the %s core. Paging by hand works"
                          % (self.conn_msg or "no data", (p.cores or ("recommended",))[0])))
        else:
            dot = T.NEG
            rows.append(R("meta", "No connection to RetroArch. Paging by hand works. "
                                  "In RetroArch: Settings > Network > Network Commands = ON"))
        rows.append(R("meta", step.get("ch", "") + ("  ·  done" if self.progress.is_done(idx) else ""),
                      T.S2 if rows else 0))
        rows.append(R("title", step["title"], 2))
        for i, ln in enumerate(step["lines"]):
            rows.append(R("body", ln, T.S2 if i == 0 else T.S1))
        for i, ln in enumerate(x for x in pv.get("nav", ()) if x):
            rows.append(R("mono", ln, T.S3 if i == 0 else T.S1))
        for i, ln in enumerate(pv.get("warn", ())):
            rows.append(R("warn", ln, T.S3 if i == 0 else T.S1))
        if self.view is not None:
            rows.append(R("link", "Browsing. Back to the current step (A)", T.S3, "auto"))
        sh = pv.get("short") or {}
        nav = sh.get("nav") or next((x for x in reversed(pv.get("nav", ())) if x), "")
        srows = [R("mono", nav, 0)] if nav and g is not None else []
        if g is None:
            srows.append(R("meta", {"nostate": "Load a save or start a game", "nocore": "No memory data from RetroArch"}.get(
                self.conn, "No connection to RetroArch"), 0))
        srows += [R("warn", ln, T.S1) for ln in pv.get("warn", ())]
        if self.view is not None:
            srows.append(R("link", "Browsing. Back to the current step (A)", T.S1, "auto"))
        P["guide"].set("Step %d of %d" % (idx + 1, len(p.steps)), rows, dot,
                       short=("flag", "%d/%d  %s" % (idx + 1, len(p.steps), step["title"]), srows, dot))

        rows = []
        if "tracker" in self.modules and self.show["tracker"] and self.ach is not None:
            near = []
            for a in self.ach.items:
                pr = self.ach.progress.get(a["id"])
                if pr and pr[1] > 0 and a["id"] not in self.ach.unlocked and not a.get("secret"):
                    near.append((pr[0] / float(pr[1]), a, pr))
            near.sort(key=lambda x: -x[0])
            for i, (_, a, pr) in enumerate(near[:3]):
                rows.append(R("strong", a["title"], T.S2 if i else 0))
                rows.append(R("mono", "%s / %s   +%d points" % ("{:,}".format(pr[0]), "{:,}".format(pr[1]), a["points"]), 0))
            rows = rows or [R("meta", "Nothing in progress yet")]
            first = "%s  %s / %s" % (near[0][1]["title"], "{:,}".format(near[0][2][0]), "{:,}".format(near[0][2][1])) \
                if near else "Nothing in progress yet"
        P["tracker"].set("Closest trophies", rows, short=("trophy", first, [], None) if rows else None)

        rows = []
        if g is not None and self.show["self"]:
            rows = [R("strong", x) for x in (pv.get("stats"),) if x]
            rows += [R("body", x) for x in (pv.get("gear"),) if x]
            rows += [R("meta", x, T.S2 if i == 0 else T.S1) for i, x in enumerate(pv.get("self", ()))]
            rows += [R("meta", x, T.S2 if i == 0 else T.S1) for i, x in enumerate(self.info)]
        P["hero"].set(pv.get("location", p.title), rows,
                      short=("heart", sh.get("stats") or pv.get("stats") or "", [], None))

        b = pv.get("battle") if self.show["battle"] else None
        rows = []
        if b:
            if b.get("frac") is not None:
                rows.append(R("bar", b["frac"]))
            rows += [R("body", x, T.S2 if i == 0 else T.S1) for i, x in enumerate(b.get("lines", ()))]
            rows = rows or [R("body", "In battle")]
        P["battle"].set(b["title"] if b else "", rows,
                        short=("sword", b["title"], ([R("bar", b["frac"], T.S1)] if b.get("frac") is not None else [])
                               + ([R("mono", b["short"], T.S1)] if b.get("short") else []), None) if b else None)

        spec = pv.get("map") if self.show["map"] else None
        P["map"].tools["zoom"].set("minus" if self.show["zoom"] else "plus")
        P["map"].set("Map", [R("map", spec)] if spec else [],
                     short=("pin", pv.get("location", "Map"), [R("map", spec, T.S1)], None) if spec else None)

        notes = pv.get("notes", ()) if self.show["loc"] else ()
        first = notes[0] if notes else ""
        P["notes"].set("Notes", [R("body", x, T.S2) for x in notes],
                       short=("note", (first if len(first) <= 64 else first[:62].rstrip() + "...")
                              + ("  (+%d more)" % (len(notes) - 1) if len(notes) > 1 else ""), [], None))

        rows, title = [], "Achievements"
        if self.show["ach"] and self.ach is not None and self.ach.items:
            A = self.ach
            groups = self._groups()
            self.ach_page %= len(groups)
            grp = groups[self.ach_page]
            mine = [a for a in A.items if a.get("group", "") == grp]
            got = sum(1 for a in mine if a["id"] in A.unlocked)
            title = "Achievements  %d / %d" % (A.count(), len(A.items))
            rows.append(R("meta", "%s · %d of %d · group %d of %d" % (grp or "General", got, len(mine),
                                                                     self.ach_page + 1, len(groups)), 0))
            for a in mine:
                when = A.unlocked.get(a["id"])
                if when:                    # earned: a trophy in the colour of its grade
                    g_ = grade(a["points"])
                    rows.append(R("irow", ("trophy", T.TROPHY[g_], "strong", a["title"]), T.S2))
                    rows.append(R("irow", (None, None, "meta", "%s · +%d points · %s · earned %s" % (
                        a["text"], a["points"], g_, time.strftime("%d %b", time.localtime(when)))), 0))
                elif a.get("secret"):
                    rows.append(R("irow", (None, None, "body", "Hidden achievement"), T.S2))
                    rows.append(R("irow", (None, None, "meta", "Shown when you earn it · %d points" % a["points"]), 0))
                else:
                    pr = A.progress.get(a["id"])
                    rows.append(R("irow", (None, None, "body", a["title"]), T.S2))
                    rows.append(R("irow", (None, None, "meta", "%s · %s%d points" % (
                        a["text"], "%s / %s · " % ("{:,}".format(pr[0]), "{:,}".format(pr[1])) if pr and pr[1] > 1 else "",
                        a["points"])), 0))
        short = None
        if rows:
            near = [(pr[0] / float(pr[1]), a, pr) for a in A.items for pr in (A.progress.get(a["id"]),)
                    if pr and pr[1] > 1 and a["id"] not in A.unlocked and not a.get("secret")]
            near.sort(key=lambda x: -x[0])
            short = ("trophy", "%d / %d  ·  %d points" % (A.count(), len(A.items), A.points()),
                     [R("meta", "Next: %s  %s / %s" % (near[0][1]["title"], "{:,}".format(near[0][2][0]),
                                                      "{:,}".format(near[0][2][1])), 0)] if near else [], None)
        P["ach"].set(title, rows, short=short)

        rows = []
        if self.show["log"]:
            for i, (when, text) in enumerate(reversed(self.log[-LOG_ROWS:])):
                rows.append(R("body" if i == 0 else "meta", "%s  %s" % (time.strftime("%H:%M", time.localtime(when)), text),
                              0 if i == 0 else 2))
            rows = rows or [R("meta", "Nothing has happened yet. Wins, levels, items, steps and achievements show up here")]
        last = self.log[-1] if self.log else None
        P["log"].set("Log", rows, short=("list", "%s  %s" % (time.strftime("%H:%M", time.localtime(last[0])), last[1])
                                          if last else "Nothing has happened yet", [], None))
        if self.atlas is not None:
            self.atlas.update(p.atlas(g, ctx))
        self.layout()

    def layout(self):
        """Docked modules stack under the guide; torn-off ones stay where they were put."""
        gx, gy = self.ui.get("pos", [40, 40])
        sw, sh = self.master.winfo_screenwidth(), self.master.winfo_screenheight() - 48     # keep clear of the taskbar
        x, y, colw, side = gx, gy, 0, 1
        for name in ORDER:
            pan = self.panels[name]
            if not pan.shown:
                continue
            if name != "guide" and pan.free:
                pan.place(pan.cfg["x"], pan.cfg["y"])
                continue
            if y > gy and y + pan.h > sh:           # the column is full: continue in one beside it
                if side == 1 and x + colw + GAP + pan.w > sw:
                    side = -1
                x = x + colw + GAP if side == 1 else x - GAP - pan.w
                y, colw = gy, 0
            pan.place(x, y)
            y += pan.h + GAP
            colw = max(colw, pan.w)
