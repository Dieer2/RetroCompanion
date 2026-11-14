"""The full-size map: one large always-on-top window, the same for every game.

It draws what a plugin's atlas() returns and knows nothing about any game:

    {"here": map id or None, "player": (x, y) or None,
     "filters": [(key, label)],              what can be switched on and off
     "legend": [(status, label)],
     "order": [map id],                      the list of maps, in this order
     "maps": {id: {"name": str, "status": str,
                   "rows": [str], "palette": {char: colour},     one character per tile
                   "notes": [str],           shown while nothing is selected
                   "marks": [mark], "areas": [(x0, y0, x1, y1, [str])],
                   "path": [(x, y)], "rects": [(x, y, colour)]}}}

    mark = {"x", "y", "kind": a filter key, "name": str, "status": str, "lines": [str],
            "goto": map id or None, "label": show the name on the map}

A status is one of: now (the current step is here), todo (something is still open), later
(needed later in the walkthrough: drawn faint), done (nothing left), optional (never
needed), info (a chest, a staircase). Two filter keys belong to the window itself: "route"
(the path) and "names" (the labels); "zone" draws the borders of the areas.

Drag the map to move it, turn the wheel to zoom, click a mark for what is there, double-click
one that leads to another map to open that map. Esc closes the window.
"""
import sys
from tkinter import font as tkfont

from . import theme as T

SIDE = 320             # width of the column beside the map
LABEL_Z = 12           # the names of small things (chests, stairs) show from this zoom


class Atlas:
    def __init__(self, ov, data):
        tk = self.tk = ov.tk
        self.ov = ov
        self.cfg = ov.ui.setdefault("atlas", {})
        self.off = set(self.cfg.get("off", ["zone"]))
        self.data = data
        self.shown = None           # the map on screen
        self.follow = True          # keep showing the map the player is on
        self.z = {}                 # zoom per map
        self.sel = None             # (map, x, y, name) of the selected mark
        self.tile = None            # a clicked tile without a mark
        self.base, self.img, self.img_key, self.sig = {}, None, None, None
        self.closed = False

        win = self.win = tk.Toplevel(ov.master)
        win.withdraw()
        win.title("%s: map" % ov.p.title)
        win.configure(bg=T.hair(T.CARD))
        if sys.platform != "darwin":
            win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-alpha", max(0.95, ov.alpha))
        except tk.TclError:
            pass
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight() - 48
        n = self.n = ov.fsize
        outer = tk.Frame(win, bg=T.CARD)
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        head = tk.Frame(outer, bg=T.CARD)
        head.pack(fill="x")
        self.title = tk.Label(head, bg=T.CARD, fg=T.TEXT2, anchor="w", font=(T.FONT, n))
        self.title.pack(side="left", fill="x", expand=True, padx=(T.S3, T.S1))
        T.IconButton(tk, head, "close", self.close).c.pack(side="right", padx=(0, T.S2), pady=T.S1)
        T.IconButton(tk, head, "plus", lambda: self.zoom(+1)).c.pack(side="right", pady=T.S1)
        T.IconButton(tk, head, "minus", lambda: self.zoom(-1)).c.pack(side="right", pady=T.S1)
        T.IconButton(tk, head, "pin", self.go_here).c.pack(side="right", pady=T.S1)
        tk.Frame(outer, bg=T.hair(T.CARD), height=1).pack(fill="x")
        win.update_idletasks()
        self.ch = ch = max(360, sh - 2 * T.S6 - head.winfo_reqheight() - 3)
        self.cw = cw = max(360, min(sw - 2 * T.S6 - SIDE - 3, ch))        # as large as the screen allows, square
        self.fonts = {s: tkfont.Font(root=win, family=T.FONT, size=s) for s in (n, n - 1)}
        body = tk.Frame(outer, bg=T.CARD)
        body.pack(fill="both", expand=True)
        c = self.c = tk.Canvas(body, width=cw, height=ch, bg=T.DEEP, highlightthickness=0, cursor="fleur")
        c.pack(side="left")
        tk.Frame(body, bg=T.hair(T.CARD), width=1).pack(side="left", fill="y")
        side = tk.Frame(body, bg=T.CARD, width=SIDE, height=ch)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        wrap = SIDE - 2 * T.S3

        def lab(fg, font, **kw):
            w = tk.Label(side, bg=T.CARD, fg=fg, font=font, anchor="w", justify="left", wraplength=wrap)
            w.pack(fill="x", padx=T.S3, **kw)
            return w

        self.d_name = lab(T.TEXT, (T.FONT, n + 3), pady=(T.S3, 0))
        self.d_state = lab(T.MUTED, (T.MONO, n - 1), pady=(2, 0))
        self.d_text = lab(T.TEXT2, (T.FONT, n), pady=(T.S2, 0))
        self.d_link = lab(T.MUTED, (T.FONT, n - 1, "underline"), pady=(T.S2, 0))
        self.d_link.configure(cursor="hand2")
        self.d_link.bind("<Button-1>", lambda e: self.open_link())
        # bottom up: legend, the list of maps, the filters; the details above take what is left
        foot = tk.Frame(side, bg=T.CARD)
        foot.pack(side="bottom", fill="x", padx=T.S3, pady=(0, T.S3))
        tk.Label(foot, text="Drag to move · wheel to zoom · click a mark · Esc closes", bg=T.CARD, fg=T.MUTED,
                 font=(T.FONT, n - 1), anchor="w", justify="left", wraplength=wrap).pack(fill="x", pady=(T.S2, 0))
        leg = tk.Frame(side, bg=T.CARD)
        leg.pack(side="bottom", fill="x", padx=T.S3)
        for status, text in data.get("legend", ()):
            row = tk.Frame(leg, bg=T.CARD)
            row.pack(fill="x")
            dot = tk.Canvas(row, width=16, height=16, bg=T.CARD, highlightthickness=0)
            dot.pack(side="left")
            self._marker(dot, 8, 8, 5, status, "place")
            tk.Label(row, text=text, bg=T.CARD, fg=T.MUTED, font=(T.FONT, n - 1), anchor="w").pack(side="left", padx=(T.S1, 0))
        tk.Frame(side, bg=T.hair(T.CARD), height=1).pack(side="bottom", fill="x", pady=T.S2)
        lb = self.lb = tk.Listbox(side, bg=T.CARD, fg=T.TEXT2, font=(T.FONT, n), height=13, bd=0, highlightthickness=0,
                                  activestyle="none", selectbackground=T.RAISED, selectforeground=T.TEXT,
                                  exportselection=False)
        lb.pack(side="bottom", fill="x", padx=T.S3)
        lb.bind("<<ListboxSelect>>", self.pick)
        tk.Label(side, text="Maps", bg=T.CARD, fg=T.MUTED, font=(T.FONT, n - 1), anchor="w").pack(
            side="bottom", fill="x", padx=T.S3, pady=(0, T.S1))
        tk.Frame(side, bg=T.hair(T.CARD), height=1).pack(side="bottom", fill="x", pady=T.S2)
        fl = tk.Frame(side, bg=T.CARD)
        fl.pack(side="bottom", fill="x", padx=T.S3)
        self.boxes = {}
        for i, (key, text) in enumerate(data.get("filters", ())):
            row = tk.Frame(fl, bg=T.CARD, cursor="hand2")
            row.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, T.S3))
            box = tk.Canvas(row, width=16, height=16, bg=T.CARD, highlightthickness=0)
            box.pack(side="left")
            t = tk.Label(row, text=text, bg=T.CARD, fg=T.TEXT2, font=(T.FONT, n - 1), anchor="w")
            t.pack(side="left", padx=(T.S1, 0))
            self.boxes[key] = box
            for w in (row, box, t):
                w.bind("<Button-1>", lambda e, k=key: self.toggle(k))
        tk.Label(side, text="Show", bg=T.CARD, fg=T.MUTED, font=(T.FONT, n - 1), anchor="w").pack(
            side="bottom", fill="x", padx=T.S3, pady=(0, T.S1))
        tk.Frame(side, bg=T.hair(T.CARD), height=1).pack(side="bottom", fill="x", pady=T.S2)
        self._paint_boxes()

        for w in (head, self.title):
            w.bind("<ButtonPress-1>", self._grab)
            w.bind("<B1-Motion>", self._drag)
        c.bind("<ButtonPress-1>", self._press)
        c.bind("<B1-Motion>", self._pan)
        c.bind("<ButtonRelease-1>", self._release)
        c.bind("<Double-Button-1>", lambda e: self.open_link())
        c.bind("<MouseWheel>", lambda e: self.zoom(1 if e.delta > 0 else -1, e))
        c.bind("<Button-4>", lambda e: self.zoom(1, e))
        c.bind("<Button-5>", lambda e: self.zoom(-1, e))
        for key, fn in (("<Escape>", self.close), ("f", self.close), ("<plus>", lambda: self.zoom(1)),
                        ("<minus>", lambda: self.zoom(-1))):
            win.bind(key, lambda e, f=fn: f())

        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry("%dx%d+%d+%d" % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 2)))
        win.deiconify()
        win.attributes("-topmost", True)
        win.focus_set()
        self.show(data.get("here") if data.get("here") in data["maps"] else data["order"][0], center=True)

    # -- window ----------------------------------------------------------------
    def close(self):
        if not self.closed:
            self.closed = True
            self.ov.atlas = None
            try:
                self.win.destroy()
            except self.tk.TclError:
                pass

    def _grab(self, e):
        self._off = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag(self, e):
        self.win.geometry("+%d+%d" % (e.x_root - self._off[0], e.y_root - self._off[1]))

    # -- filters, list -----------------------------------------------------------
    def on(self, key):
        return key not in self.off

    def toggle(self, key):
        self.off ^= {key}
        self.cfg["off"] = sorted(self.off)
        self.ov.save_ui()
        self._paint_boxes()
        self.draw(force=True)

    def _paint_boxes(self):
        for key, box in self.boxes.items():
            box.delete("all")
            box.create_rectangle(2.5, 2.5, 13.5, 13.5, outline=T.MUTED)
            if self.on(key):
                box.create_line(5, 8.5, 7.2, 10.7, 11, 5.5, fill=T.TEXT, width=1.5, capstyle="round", joinstyle="round")

    def _fill_list(self):
        d, lb = self.data, self.lb
        names = ["%s%s" % (d["maps"][m]["name"], "  · you are here" if m == d.get("here") else "") for m in d["order"]]
        if names != list(lb.get(0, "end")):
            lb.delete(0, "end")
            for nm in names:
                lb.insert("end", nm)
        for i, m in enumerate(d["order"]):
            lb.itemconfigure(i, fg=self._tint(d["maps"][m].get("status"))[1])
        lb.selection_clear(0, "end")
        if self.shown in d["order"]:
            i = d["order"].index(self.shown)
            lb.selection_set(i)
            lb.see(i)

    def pick(self, e=None):
        cur = self.lb.curselection()
        if cur:
            self.follow = False
            self.show(self.data["order"][cur[0]], center=True)

    def go_here(self):
        self.follow = True
        if self.data.get("here") in self.data["maps"]:
            self.show(self.data["here"], center=True)

    def open_link(self):
        mk = self._selected()
        if mk and mk.get("goto") in self.data["maps"]:
            self.follow = False
            self.show(mk["goto"], center=True)

    # -- data ------------------------------------------------------------------
    def update(self, data):
        """New data from the plugin (called on every tick while the window is open)."""
        if self.closed or not data:
            return
        moved = data.get("here") != self.data.get("here")
        self.data = data
        if moved and self.follow and data.get("here") in data["maps"]:
            self.show(data["here"], center=True)
        else:
            self.draw()

    def show(self, m, center=False):
        self.shown = m
        self.sel = self.tile = None
        mp = self.data["maps"][m]
        w, h = len(mp["rows"][0]), len(mp["rows"])
        if m not in self.z:
            self.z[m] = max(1, min(self.cw // w, self.ch // h, 40))
        self.draw(force=True)
        if center:
            pl = self.data.get("player") if m == self.data.get("here") else None
            self.center(*(pl or (w / 2.0, h / 2.0)))

    def _dims(self):
        mp = self.data["maps"][self.shown]
        z = self.z[self.shown]
        W, H = len(mp["rows"][0]) * z, len(mp["rows"]) * z
        return z, W, H, -max(0, (self.cw - W) // 2), -max(0, (self.ch - H) // 2)

    def center(self, tx, ty):
        z, W, H, X0, Y0 = self._dims()
        tw, th = max(self.cw, W), max(self.ch, H)
        self.c.xview_moveto(max(0.0, (tx * z + z / 2.0 - self.cw / 2.0 - X0) / tw))
        self.c.yview_moveto(max(0.0, (ty * z + z / 2.0 - self.ch / 2.0 - Y0) / th))

    def zoom(self, d, e=None):
        mp = self.data["maps"][self.shown]
        w, h = len(mp["rows"][0]), len(mp["rows"])
        z0 = self.z[self.shown]
        top = max(2, min(40, 2600 // max(w, h)))
        z = max(1, min(top, z0 + d * (1 if z0 < 8 else 2 if z0 < 20 else 4)))
        if z == z0:
            return
        ex, ey = (e.x, e.y) if e is not None else (self.cw // 2, self.ch // 2)
        tx, ty = self.c.canvasx(ex) / float(z0), self.c.canvasy(ey) / float(z0)       # the tile under the pointer stays put
        self.z[self.shown] = z
        self.draw(force=True)
        _, W, H, X0, Y0 = self._dims()
        self.c.xview_moveto(max(0.0, (tx * z - ex - X0) / max(self.cw, W)))
        self.c.yview_moveto(max(0.0, (ty * z - ey - Y0) / max(self.ch, H)))

    # -- pointer ---------------------------------------------------------------
    def _press(self, e):
        self._down = (e.x, e.y)
        self._moved = False
        self.c.scan_mark(e.x, e.y)

    def _pan(self, e):
        if abs(e.x - self._down[0]) + abs(e.y - self._down[1]) > 4:
            self._moved = True
        if self._moved:
            self.c.scan_dragto(e.x, e.y, gain=1)

    def _release(self, e):
        if self._moved:
            return
        z = self.z[self.shown]
        px, py = self.c.canvasx(e.x), self.c.canvasy(e.y)
        best, bd = None, max(14, z) ** 2
        for mk in self._marks():
            dd = (mk["x"] * z + z / 2.0 - px) ** 2 + (mk["y"] * z + z / 2.0 - py) ** 2
            if dd < bd:
                best, bd = mk, dd
        mp = self.data["maps"][self.shown]
        tx, ty = int(px // z), int(py // z)
        self.sel = (self.shown, best["x"], best["y"], best["name"]) if best else None
        self.tile = None if best or not (0 <= tx < len(mp["rows"][0]) and 0 <= ty < len(mp["rows"])) else (tx, ty)
        self.draw(force=True)

    # -- drawing ---------------------------------------------------------------
    def _marks(self):
        return [mk for mk in self.data["maps"][self.shown].get("marks", ()) if self.on(mk["kind"])]

    def _selected(self):
        if self.sel and self.sel[0] == self.shown:
            for mk in self.data["maps"][self.shown].get("marks", ()):
                if (mk["x"], mk["y"], mk["name"]) == self.sel[1:]:
                    return mk
        return None

    def _tint(self, status):
        """(marker colour, text colour) of a status."""
        acc = T.accent_text(self.ov.p.accent)
        return {"now": (acc, acc), "todo": (T.TEXT, T.TEXT), "later": (T.mix(T.MUTED, T.CARD, 0.35), T.MUTED),
                "done": (T.POS, T.TEXT2), "optional": (T.TEXT2, T.TEXT2)}.get(status, (T.TEXT2, T.TEXT2))

    def _marker(self, c, x, y, r, status, kind, tags=()):
        col = self._tint(status)[0]
        if status == "info":                # small things: a chest is a square, a way out a diamond
            if kind == "chest":
                c.create_rectangle(x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7, fill="#f2c14e", outline="#12110f", tags=tags)
            else:
                c.create_polygon(x, y - r, x + r, y, x, y + r, x - r, y, fill=T.CARD, outline=T.TEXT, tags=tags)
        elif status == "done":
            c.create_oval(x - r, y - r, x + r, y + r, fill="#12110f", outline=col, width=1.5, tags=tags)
            c.create_line(x - r * 0.45, y + r * 0.05, x - r * 0.1, y + r * 0.4, x + r * 0.5, y - r * 0.35,
                          fill=col, width=1.5, capstyle="round", joinstyle="round", tags=tags)
        elif status == "optional":
            c.create_oval(x - r, y - r, x + r, y + r, fill="#12110f", outline=col, width=1.5, dash=(2, 2), tags=tags)
        elif status == "now":
            c.create_oval(x - r - 4, y - r - 4, x + r + 4, y + r + 4, outline=col, width=2, tags=tags)
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="#12110f", tags=tags)
        else:
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="#12110f", tags=tags)

    def _text(self, x, y, text, fg, anchor="w", size=None):
        font = (T.FONT, size or self.n)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 1), (0, -1), (1, 0), (-1, 0)):
            self.c.create_text(x + dx, y + dy, text=text, fill="#12110f", font=font, anchor=anchor, tags="o")
        self.c.create_text(x, y, text=text, fill=fg, font=font, anchor=anchor, tags="o")

    def draw(self, force=False):
        if self.closed:
            return
        d, m = self.data, self.shown
        if m not in d["maps"]:
            m = self.shown = d["order"][0]
        mp = d["maps"][m]
        pl = d.get("player") if m == d.get("here") else None
        sig = repr((m, self.z.get(m), mp.get("marks"), mp.get("path"), mp.get("rects"), pl, mp.get("status"),
                    d.get("here"), sorted(self.off), self.sel, self.tile))
        if sig == self.sig and not force:
            return
        self.sig = sig
        c = self.c
        z, W, H, X0, Y0 = self._dims()
        if self.img_key != (m, z):
            if m not in self.base:
                rows, pal = mp["rows"], mp["palette"]
                img = self.tk.PhotoImage(width=len(rows[0]), height=len(rows))
                img.put(" ".join("{" + " ".join(pal.get(ch, "#000000") for ch in row) + "}" for row in rows))
                self.base[m] = img
            img = self.tk.PhotoImage()
            img.tk.call(img, "copy", self.base[m], "-zoom", z, z)
            self.img, self.img_key = img, (m, z)
            c.delete("all")
            c.create_image(0, 0, image=img, anchor="nw", tags="m")
            c.configure(scrollregion=(X0, Y0, X0 + max(self.cw, W), Y0 + max(self.ch, H)))
        c.delete("o")

        def pos(x, y):
            return x * z + z / 2.0, y * z + z / 2.0

        for x, y, color in mp.get("rects", ()):
            c.create_rectangle(x * z, y * z, x * z + z, y * z + z, fill=color, outline="", tags="o")
        if self.on("zone"):
            for x0, y0, x1, y1, _ in mp.get("areas", ()):
                c.create_rectangle(x0 * z, y0 * z, (x1 + 1) * z, (y1 + 1) * z, outline="#12110f", dash=(4, 4), tags="o")
        path = mp.get("path") or ()
        if self.on("route") and len(path) >= 2:
            flat = []
            for x, y in path:
                flat.extend(pos(x, y))
            c.create_line(*flat, fill="#12110f", width=max(4, z // 3 + 2), capstyle="round", joinstyle="round", tags="o")
            c.create_line(*flat, fill=T.ROUTE, width=max(2, z // 3), capstyle="round", joinstyle="round", tags="o")
        sel = self._selected()
        r = max(4, min(8, z * 0.6))
        marks = self._marks()
        for mk in sorted(marks, key=lambda k: k["status"] in ("now", "todo")):      # what matters is drawn last, on top
            px, py = pos(mk["x"], mk["y"])
            small = mk["status"] == "info"
            self._marker(c, px, py, r * 0.8 if small else r, mk["status"], mk["kind"], tags="o")
            if mk is sel:
                c.create_oval(px - r - 7, py - r - 7, px + r + 7, py + r + 7, outline=T.TEXT, width=1, dash=(3, 3), tags="o")
        if self.on("names"):
            # a name goes right of its mark, or left, below or above when that spot is taken
            taken = [(px - r, py - r, px + r, py + r) for px, py in (pos(mk["x"], mk["y"]) for mk in marks)]
            rank = {"now": 0, "todo": 1, "done": 2, "optional": 3, "later": 4}
            for mk in sorted(marks, key=lambda k: (k is not sel, not k.get("label"), rank.get(k["status"], 5))):
                must = mk.get("label") or mk is sel
                if not (must or z >= LABEL_Z):
                    continue
                size = self.n if mk.get("label") else self.n - 1
                f = self.fonts[size]
                tw, th = f.measure(mk["name"]), f.metrics("linespace")
                px, py = pos(mk["x"], mk["y"])
                spots = [(px + r + 5, py - th / 2.0), (px - r - 5 - tw, py - th / 2.0),
                         (px - tw / 2.0, py + r + 3), (px - tw / 2.0, py - r - 3 - th)]
                ok = [s for s in spots if 0 <= s[0] and s[0] + tw <= W and not any(
                    s[0] < q[2] and q[0] < s[0] + tw and s[1] < q[3] and q[1] < s[1] + th for q in taken)]
                if not ok and not must:
                    continue
                x, y = (ok or spots)[0]
                taken.append((x, y, x + tw, y + th))
                self._text(x, y, mk["name"], self._tint(mk["status"])[1], "nw", size)
        if pl:
            px, py = pos(*pl)
            q = max(4, min(9, z * 0.5))
            c.create_rectangle(px - q, py - q, px + q, py + q, fill="#ffffff", outline=T.NEG, width=2, tags="o")
            if self.on("names"):
                self._text(px, py - q - 9, "You", "#ffffff", "center", self.n - 1)

        # the column beside the map
        self.title.configure(text="Map  ·  %s" % mp["name"])
        legend = dict(d.get("legend", ()))
        link = ""
        if sel:
            name, state, lines = sel["name"], legend.get(sel["status"], ""), sel.get("lines", ())
            if sel.get("goto") in d["maps"]:
                link = "Open the map of %s" % d["maps"][sel["goto"]]["name"]
        elif self.tile:
            name, state = mp["name"], "tile %d, %d" % self.tile
            lines = [ln for x0, y0, x1, y1, ls in mp.get("areas", ())
                     if x0 <= self.tile[0] <= x1 and y0 <= self.tile[1] <= y1 for ln in ls] or ["Nothing marked on this tile"]
        else:
            name, state, lines = mp["name"], legend.get(mp.get("status"), ""), mp.get("notes", ())
        self.d_name.configure(text=name)
        self.d_state.configure(text=state, fg=self._tint(sel["status"] if sel else mp.get("status"))[1] if state else T.MUTED)
        self.d_text.configure(text="\n\n".join(lines))
        self.d_link.configure(text=link)
        self._fill_list()
