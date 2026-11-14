"""The library window: every supported game in one place, with launch, progress, play time
and the walkthrough. It also owns the RetroArch polling loop and opens the overlay when a
known game is running."""
import json
import os
import queue
import sys
import threading
import time
import webbrowser

from . import APP_NAME, SUPPORT_URL, VERSION, retroarch as ra
from . import moby
from .account import Account, AccountError
from .achievements import Achievements
from .merge import merge_into, snapshot
from .overlay import Overlay
from .profile import Profile, SHOP, GRADES, grade, level_floor
from .plugin import Progress
from .store import Store
from . import theme as T

HOTKEYS = {0x27: "next", 0x25: "prev", 0x44: "done", 0x48: "hide", 0x41: "auto", 0x4C: "loc",
           0x4D: "map", 0x53: "self", 0x5A: "zoom"}


LOG_KEEP = 300                    # log lines kept per game (this computer only, not synced)
HOTKEY_APPS = ("retroarch",)      # program names (lowercase, start of the file name) the hotkeys work in


def foreground_program():
    """File name (lowercase) of the program owning the active window on Windows.
    "" if there is no active window, None if the name cannot be read."""
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        return os.path.basename(sys.executable).lower()
    h = kernel32.OpenProcess(0x1000, False, pid.value)       # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return None
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)


def hotkeys_wanted(overlay_open, program):
    """The Ctrl+Shift keys are taken from the system only while they can mean something:
    an overlay is open and the emulator is the active window. Everywhere else they stay with
    the program the user is working in (Ctrl+Shift+S and friends keep working there)."""
    return bool(overlay_open and program and program.startswith(HOTKEY_APPS))


def hotkey_thread(q, overlay_open, stop):
    """Global overlay hotkeys on Windows (Ctrl+Shift+key). Does nothing elsewhere.
    overlay_open: callable, True while an overlay window exists."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        ids = {i: act for i, (vk, act) in enumerate(HOTKEYS.items(), 1)}
        vks = {i: vk for i, (vk, act) in enumerate(HOTKEYS.items(), 1)}
        held = False
        msg = wintypes.MSG()
        while not stop.is_set():
            want = hotkeys_wanted(overlay_open(), foreground_program() if overlay_open() else "")
            if want and not held:
                for i, vk in vks.items():
                    user32.RegisterHotKey(None, i, 0x0002 | 0x0004 | 0x4000, vk)   # CTRL | SHIFT | NOREPEAT
            elif held and not want:
                for i in vks:
                    user32.UnregisterHotKey(None, i)
            held = want
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):          # PM_REMOVE
                if msg.message == 0x0312 and msg.wParam in ids and held:
                    q.put(("key", ids[msg.wParam]))
            stop.wait(0.05)
    except Exception:
        pass


def fmt_time(sec):
    sec = int(sec or 0)
    if sec < 60:
        return "0 min" if sec == 0 else "under 1 min"
    h, m = sec // 3600, (sec % 3600) // 60
    return "%d h %02d min" % (h, m) if h else "%d min" % m


def fmt_when(ts):
    if not ts:
        return "never"
    lt, now = time.localtime(ts), time.localtime()
    if (lt.tm_year, lt.tm_yday) == (now.tm_year, now.tm_yday):
        return time.strftime("today %H:%M", lt)
    return time.strftime("%Y-%m-%d", lt)


class App:
    def __init__(self, store=None, port=None):
        import tkinter as tk
        from games import load_plugins
        self.tk = tk
        self.store = store or (Store(os.environ["RC_STORE"]) if os.environ.get("RC_STORE") else Store())
        self.port = port or int(os.environ.get("RETROARCH_PORT", ra.DEFAULT_PORT))
        self.host = os.environ.get("RETROARCH_HOST", "127.0.0.1")
        self.plugins, self.plugin_errors = load_plugins()
        self.by_id = {p.id: p for p in self.plugins}
        for p in self.plugins:                   # tables read earlier, or a ROM chosen before tables were read
            rom = self.store.game(p.id).get("rom")
            if p.data_status() and rom and os.path.isfile(rom):
                try:
                    p.prepare(rom)
                except Exception:
                    pass
        self.progress ={p.id: Progress(p, self.store.game(p.id), self.mark_dirty) for p in self.plugins}
        self.ach = {p.id: Achievements(p, self.store.game(p.id), self.mark_dirty) for p in self.plugins}
        self.profile = Profile(self.store.data["profile"], self.ach, self.store.save)
        self._theme = self.profile.theme()
        T.apply(self._theme)
        self.account = Account(self.store.settings)
        self._sync_busy = False
        self._unsynced = False      # something changed since the last successful sync
        self._last_sync = 0.0
        self._form = None           # the open account form, if any
        self._board = None          # the open leaderboard window, if any
        self.tab = "walk"           # what the lower half of a game page shows: walk | ach | about
        self._moby_busy = False
        self._moby_err = ""
        self._profile_win = None
        self.sel = self.plugins[0]
        self.q = queue.Queue()
        self.stop = threading.Event()
        self.forced = None          # plugin id attached by hand (Play / Overlay button)
        self.dismissed = None       # plugin id whose overlay the user closed during this run of the game
        self.overlay = None
        self.overlay_pid = None
        self.status = None          # last GET_STATUS
        self.live_pid = None        # plugin id of the running game
        self.live_conn = "offline"
        self.last_frame = 0.0
        self._prev = {}             # game id -> the state before the latest one, for the plugin's events()
        self.dirty = False
        self.last_save = time.time()
        self._sig = None
        self._banner_img = self._banner_key = None
        self.message = ""

        root = self.root = tk.Tk()
        root.title(APP_NAME)
        T.init_fonts(root)
        root.configure(bg=T.PAGE)
        root.geometry("1040x720")
        root.minsize(860, 560)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.build()
        threading.Thread(target=self.net_loop, daemon=True).start()
        threading.Thread(target=hotkey_thread, args=(self.q, lambda: self.overlay is not None, self.stop),
                         daemon=True).start()
        self.select(self.sel)
        root.after(150, self.tick)
        root.after(1500, self.sync)

    # ------------------------------------------------------------------ widgets
    def build(self):
        tk = self.tk
        S1, S2, S3, S4, S6 = T.S1, T.S2, T.S3, T.S4, T.S6
        side = tk.Frame(self.root, bg=T.DEEP, width=248)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text=APP_NAME, bg=T.DEEP, fg=T.TEXT, font=(T.FONT, 12), anchor="w").pack(
            fill="x", padx=S4, pady=(S4, 0))
        tk.Label(side, text="Library", bg=T.DEEP, fg=T.MUTED, font=(T.FONT, 9), anchor="w").pack(
            fill="x", padx=S4, pady=(S6, S2))
        self.rows = {}
        for p in self.plugins:
            row = tk.Frame(side, bg=T.DEEP, cursor="hand2")
            row.pack(fill="x", padx=S2, pady=1)
            box = tk.Frame(row, bg=T.DEEP)
            box.pack(side="left", fill="x", expand=True, padx=S2, pady=6)
            t = tk.Label(box, text=p.title, bg=T.DEEP, fg=T.TEXT, font=(T.FONT, 10), anchor="w")
            t.pack(fill="x")
            s = tk.Label(box, text="", bg=T.DEEP, fg=T.MUTED, font=(T.FONT, 9), anchor="w")
            s.pack(fill="x")
            d = T.dot(tk, row, T.DEEP, T.DEEP)
            d.pack(side="right", padx=S3)
            for w in (row, box, t, s, d):
                w.bind("<Button-1>", lambda e, p=p: self.select(p))
            self.rows[p.id] = (row, box, t, s, d)
        tk.Label(side, text="Games are plugins. README.md shows how to add one", bg=T.DEEP, fg=T.MUTED,
                 font=(T.FONT, 9), justify="left", anchor="w", wraplength=216).pack(fill="x", padx=S4, pady=(S4, 0))
        foot = tk.Frame(side, bg=T.DEEP)
        foot.pack(side="bottom", fill="x", padx=S4, pady=S4)
        line = tk.Frame(foot, bg=T.DEEP)
        line.pack(fill="x", pady=(0, S3))
        self.conn_dot = T.dot(tk, line, T.DEEP)
        self.conn_dot.pack(side="left", anchor="n", pady=5)
        self.conn_lbl = tk.Label(line, text="", bg=T.DEEP, fg=T.TEXT2, font=(T.FONT, 9), anchor="w", justify="left",
                                 wraplength=196)
        self.conn_lbl.pack(side="left", fill="x", padx=(S2, 0))
        T.button(tk, foot, "Settings", self.open_settings).pack(fill="x")
        tk.Label(foot, text="v" + VERSION, bg=T.DEEP, fg=T.MUTED, font=(T.MONO, 8), anchor="w").pack(fill="x", pady=(S2, 0))
        # the player's profile: level, points, trophies. Click opens the profile and shop window
        prof = tk.Frame(side, bg=T.DEEP, cursor="hand2")
        prof.pack(side="bottom", fill="x", padx=S4, pady=(0, S4))
        self.prof_title = tk.Label(prof, text="", bg=T.DEEP, fg=T.TEXT, font=(T.FONT, 10), anchor="w")
        self.prof_title.pack(fill="x")
        self.prof_bar = tk.Canvas(prof, height=4, bg=T.RAISED, highlightthickness=0)
        self.prof_bar.pack(fill="x", pady=(S1 + 2, S1 + 2))
        self.prof_sub = tk.Label(prof, text="", bg=T.DEEP, fg=T.MUTED, font=(T.FONT, 9), anchor="w", justify="left",
                                 wraplength=216)
        self.prof_sub.pack(fill="x")
        for w in (prof, self.prof_title, self.prof_bar, self.prof_sub):
            w.bind("<Button-1>", lambda e: self.open_profile())
        tk.Frame(side, bg=T.hair(T.DEEP), height=1).pack(side="bottom", fill="x", padx=S4, pady=(0, S4))

        main = self.main = tk.Frame(self.root, bg=T.PAGE)
        main.pack(side="left", fill="both", expand=True)
        self.banner = tk.Canvas(main, height=160, bg=T.PAGE, highlightthickness=0)
        self.banner.pack(fill="x")
        self.banner.bind("<Configure>", lambda e: self.draw_banner())
        tk.Frame(main, bg=T.hair(T.PAGE), height=1).pack(fill="x")
        act = tk.Frame(main, bg=T.PAGE)
        act.pack(fill="x", padx=S6, pady=(S4, S2))
        self.play_btn = T.button(tk, act, "Play", self.play, kind="primary", accent=self.sel.accent)
        self.play_btn.configure(padx=T.S6)
        self.play_btn.pack(side="left")
        self.ov_btn = T.button(tk, act, "Open overlay", self.toggle_overlay)
        self.ov_btn.pack(side="left", padx=(S2, 0))
        T.button(tk, act, "Choose ROM", self.choose_rom).pack(side="left", padx=(S2, 0))
        self.msg_lbl = tk.Label(main, text="", bg=T.PAGE, fg=T.MUTED, font=(T.FONT, 9), anchor="w", justify="left",
                                wraplength=700)
        self.msg_lbl.pack(fill="x", padx=S6)
        tiles = tk.Frame(main, bg=T.PAGE)
        tiles.pack(fill="x", padx=S6, pady=(S4, 0))
        self.tiles = {}
        for i, (key, label) in enumerate((("progress", "Progress"), ("ach", "Achievements"), ("time", "Play time"),
                                           ("last", "Last played"), ("seen", "Last seen"))):
            f = tk.Frame(tiles, bg=T.CARD, highlightthickness=1, highlightbackground=T.hair(T.CARD))
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else S2, 0))
            tiles.grid_columnconfigure(i, weight=3 if key == "seen" else 2, uniform="t")
            tk.Label(f, text=label, bg=T.CARD, fg=T.MUTED, font=(T.FONT, 9), anchor="w").pack(fill="x", padx=S3, pady=(S3, 0))
            v = tk.Label(f, text="", bg=T.CARD, fg=T.TEXT, font=(T.MONO, 11) if key != "seen" else (T.FONT, 11),
                         anchor="nw", justify="left", wraplength=120)
            v.pack(fill="both", expand=True, padx=S3, pady=(2, S3))
            f.bind("<Configure>", lambda e, v=v: v.configure(wraplength=max(60, e.width - 2 * T.S3 - 12)))
            self.tiles[key] = v
        self.pbar = tk.Canvas(main, height=4, bg=T.RAISED, highlightthickness=0)
        self.pbar.pack(fill="x", padx=S6, pady=(S3, 0))
        self.pbar.bind("<Configure>", lambda e: self.draw_pbar())
        hd = tk.Frame(main, bg=T.PAGE)
        hd.pack(fill="x", padx=S6, pady=(S6, S2))
        self.tabs = {}
        for key, label in (("walk", "Walkthrough"), ("ach", "Achievements"), ("about", "About")):
            b = tk.Label(hd, text=label, bg=T.PAGE, fg=T.MUTED, font=(T.FONT, 11), cursor="hand2")
            b.pack(side="left", padx=(0, S4))
            b.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self.tabs[key] = b
        self.hint_lbl = tk.Label(hd, text="", bg=T.PAGE, fg=T.MUTED, font=(T.FONT, 9))
        self.hint_lbl.pack(side="left")
        self.reset_btn = T.button(tk, hd, "Reset progress", self.reset_progress, kind="quiet")
        self.reset_btn.pack(side="right")
        wrap = tk.Frame(main, bg=T.PAGE)
        wrap.pack(fill="both", expand=True, padx=(S6, S2), pady=(0, S4))
        self.text = tk.Text(wrap, bg=T.PAGE, fg=T.TEXT, bd=0, highlightthickness=0, wrap="word", cursor="arrow",
                            font=(T.FONT, 10), padx=0, pady=2, spacing1=1, spacing3=1,
                            tabs=("32", "right", "44", "left"), selectbackground=T.RAISED, selectforeground=T.TEXT)
        sb = T.Scroll(tk, wrap, self.text)
        sb.c.pack(side="right", fill="y", padx=(S2, 0))
        self.text.configure(yscrollcommand=sb.set)
        self.text.pack(side="left", fill="both", expand=True)
        t = self.text
        t.tag_configure("ch", foreground=T.MUTED, font=(T.FONT, 9), spacing1=T.S5, spacing3=T.S1)
        t.tag_configure("head", foreground=T.TEXT, font=(T.FONT, 11), spacing1=T.S2)      # later tags win
        t.tag_configure("mark", foreground=T.MUTED, font=(T.FONT, 10))
        t.tag_configure("num", foreground=T.MUTED, font=(T.MONO, 10))
        t.tag_configure("done", foreground=T.MUTED)
        t.tag_configure("here", foreground=T.MUTED, font=(T.FONT, 9))
        t.tag_configure("line", foreground=T.TEXT2, lmargin1=44, lmargin2=44, spacing1=2)
        t.tag_configure("about", foreground=T.TEXT2, lmargin1=0, lmargin2=0, spacing1=3, tabs=("120",))
        t.tag_configure("fact", foreground=T.MUTED)

    # ------------------------------------------------------------------ game page
    def select(self, plugin):
        self.sel = plugin
        self.message = ""
        self._sig = None
        self.text.tag_configure("cur", foreground=T.accent_text(plugin.accent))
        self.draw_banner()
        self.refresh(force=True)

    def draw_banner(self):
        """Left: the game's name on calm space. Right: its world, the one colourful thing here."""
        c, p = self.banner, self.sel
        w, H, split = max(c.winfo_width(), 600), 160, 372
        c.delete("all")
        b = p.banner()
        if b:
            rows = b["rows"]
            z = max(2, -(-(w - split) // len(rows[0])))
            need = min(len(rows), -(-H // z))
            y0 = max(0, min(b["y0"], len(rows) - need))
            key = (p.id, z, y0, need)
            if key != self._banner_key:
                part = rows[y0:y0 + need]
                pal = {k: T.mix(v, T.PAGE, 0.22) for k, v in b["palette"].items()}
                img = self.tk.PhotoImage(width=len(part[0]), height=len(part))
                img.put(" ".join("{" + " ".join(pal.get(ch, "#000000") for ch in row) + "}" for row in part))
                big = self.tk.PhotoImage()
                big.tk.call(big, "copy", img, "-zoom", z, z)
                self._banner_img, self._banner_key = big, key
            c.create_image(split, 0, image=self._banner_img, anchor="nw")
            c.create_line(split, 0, split, H, fill=T.hair(T.PAGE))
        c.create_text(T.S6, 48, text=p.title, fill=T.TEXT, font=(T.FONT, 22), anchor="w")
        sub = " · ".join(str(x) for x in (p.system, p.year, p.publisher) if x)
        c.create_text(T.S6, 80, text=sub, fill=T.MUTED, font=(T.MONO, 9), anchor="w")
        c.create_text(T.S6, 96, text=p.blurb, fill=T.TEXT2, font=(T.FONT, 10), anchor="nw", width=split - 2 * T.S6)

    def draw_pbar(self):
        pr = self.progress[self.sel.id]
        w = self.pbar.winfo_width()
        self.pbar.delete("all")
        self.pbar.create_rectangle(0, 0, int(w * pr.done_count() / max(1, len(self.sel.steps))), 4,
                                   fill=T.TEXT2, outline="")

    def refresh(self, force=False):
        p = self.sel
        gs = self.store.game(p.id)
        pr = self.progress[p.id]
        st = self.status
        if st is None:
            conn, col = "RetroArch is not running, or its Network Commands are off", T.MUTED
        elif st["state"] == "CONTENTLESS":
            conn, col = "RetroArch is connected, no game loaded", T.MUTED
        elif self.live_pid:
            conn, col = "%s is %s" % (self.by_id[self.live_pid].title, st["state"].lower()), T.POS
        else:
            conn, col = "RetroArch is running “%s”, which has no plugin yet" % st["name"], T.MUTED
        running = self.live_pid == p.id
        done = tuple(pr.is_done(i) for i in range(len(p.steps)))
        ach = self.ach[p.id]
        sig = (p.id, conn, running, done, pr.current(), gs.get("rom"), int(gs.get("playtime", 0)) // 30,
               gs.get("summary"), self.message, self.overlay_pid, self.tab, ach.signature(),
               (gs.get("moby") or {}).get("fetched"), self._moby_busy, self._moby_err)
        if sig == self._sig and not force:
            return
        rebuild = (force or self._sig is None or any(self._sig[i] != sig[i] for i in (0, 3, 4, 10))
                   or (self.tab == "ach" and self._sig[11] != sig[11])
                   or (self.tab == "about" and self._sig[12:] != sig[12:]))
        self._sig = sig
        if self.tab == "walk":
            self.reset_btn.pack(side="right")
        else:
            self.reset_btn.pack_forget()
        for key, b in self.tabs.items():
            b.configure(fg=T.TEXT if key == self.tab else T.MUTED)
        self.hint_lbl.configure(text={"walk": "Click a step to tick it off by hand", "about": "",
                                      "ach": "%d of %d points" % (ach.points(), ach.total_points())}[self.tab])
        pf = self.profile
        self.prof_title.configure(text="Level %d · %s" % (pf.level(), pf.title()))
        acc = self.account.s
        who = ("Signed in as %s%s" % (acc.get("name", ""), " · rank %d" % acc["rank"] if acc.get("rank") else "")
               if self.account.signed_in else "Not signed in: trophies stay on this computer")
        self.prof_sub.configure(text="%d points to spend\n%s\n%s" % (pf.balance(), self.trophy_line(), who))
        into, span = pf.level_progress()
        self.prof_bar.update_idletasks()
        self.prof_bar.delete("all")
        self.prof_bar.create_rectangle(0, 0, int(self.prof_bar.winfo_width() * into / float(span)), 4,
                                       fill=T.TEXT2, outline="")
        self.tiles["ach"].configure(text="%d / %d" % (ach.count(), len(ach.items)))
        self.conn_lbl.configure(text=conn)
        self.conn_dot.itemconfigure("d", fill=col)
        for pid, (row, box, t, s, d) in self.rows.items():
            q = self.by_id[pid]
            bg = T.RAISED if pid == p.id else T.DEEP
            for w in (row, box, t, s, d):
                w.configure(bg=bg)
            n = self.progress[pid].done_count()
            live = self.live_pid == pid
            s.configure(text="%s · %d%% done%s" % (q.system, round(100.0 * n / max(1, len(q.steps))),
                                                    " · running" if live else ""))
            d.itemconfigure("d", fill=T.POS if live else bg)
        T.style_button(self.play_btn, "primary", p.accent)
        self.play_btn.configure(text="Running" if running else "Play")
        self.ov_btn.configure(text="Close overlay" if self.overlay_pid == p.id else "Open overlay")
        self.tiles["progress"].configure(text="%d / %d" % (sum(done), len(p.steps)))
        self.tiles["time"].configure(text=fmt_time(gs.get("playtime")))
        self.tiles["last"].configure(text=fmt_when(gs.get("last_played")))
        self.tiles["seen"].configure(text=gs.get("summary") or "Nothing yet")
        rom = gs.get("rom")
        info = self.message.lstrip("!") or p.data_status() or (
            "ROM: " + rom if rom else "No ROM chosen yet, Play will ask for it. "
                                      "A game started in RetroArch by hand is detected too")
        self.msg_lbl.configure(text=info, fg=T.NEG if self.message.startswith("!") else T.MUTED)
        self.draw_pbar()
        if rebuild:
            {"ach": self.fill_achievements, "about": self.fill_about}.get(self.tab, self.fill_walkthrough)()

    def trophy_line(self):
        t = self.profile.trophies()
        return " · ".join("%d %s" % (t[g], g) for g in reversed(GRADES) if t[g]) or "No trophies yet"

    def show_tab(self, key):
        if key != self.tab:
            self.tab = key
            self._shown_cur = None
            if key == "about":
                self.load_moby()
            self.refresh(force=True)
            if key != "walk":
                self.text.yview_moveto(0.0)

    # ------------------------------------------------------------------ MobyGames
    def load_moby(self, force=False):
        """Fetch the selected game's MobyGames entry in the background, unless a fresh one is cached."""
        p = self.sel
        key = (self.store.settings.get("moby_key") or "").strip()
        info = self.store.game(p.id).get("moby")
        fresh = info and time.time() - info.get("fetched", 0) < moby.MAX_AGE
        if not key or self._moby_busy or (fresh and not force):
            return
        self._moby_busy, self._moby_err = True, ""

        def work():
            try:
                self.q.put(("moby", p.id, moby.fetch(key, p.title, p.system, p.moby_id), ""))
            except moby.MobyError as exc:
                self.q.put(("moby", p.id, None, str(exc)))
            except Exception as exc:                      # never leave the busy flag stuck
                self.q.put(("moby", p.id, None, "MobyGames lookup failed (%s)" % exc))

        threading.Thread(target=work, daemon=True).start()

    def on_moby(self, pid, info, err):
        self._moby_busy, self._moby_err = False, err
        if info:
            self.store.game(pid)["moby"] = info
            self.store.save()

    def fill_about(self):
        t, p = self.text, self.sel
        info = self.store.game(p.id).get("moby")
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not info:
            if self._moby_busy:
                msg = "Asking MobyGames about %s" % p.title
            elif self._moby_err:
                msg = self._moby_err
            elif not (self.store.settings.get("moby_key") or "").strip():
                msg = ("Game information comes from MobyGames. Add your MobyGames API key in Settings "
                       "and this page fills in by itself")
            else:
                msg = "Nothing loaded yet"
            t.insert("end", "From MobyGames\n", "ch")
            t.insert("end", msg + "\n", "about")
        else:
            t.insert("end", "From MobyGames\n", "ch")
            facts = [("Released", info.get("released")), ("Genres", ", ".join(info.get("genres") or ())),
                     ("Developed by", ", ".join(info.get("developers") or ())),
                     ("Published by", ", ".join(info.get("publishers") or ())),
                     ("Also on", ", ".join(x for x in info.get("platforms") or () if x.casefold() != p.system.casefold())),
                     ("MobyScore", ("%.1f out of 10" % info["score"]) if info.get("score") else "")]
            for label, value in facts:
                if value:
                    t.insert("end", label + "\t", ("about", "fact"))
                    t.insert("end", str(value) + "\n", "about")
            t.insert("end", "Description\n", "ch")
            t.insert("end", (info.get("description") or "No description") + "\n", "about")
            t.insert("end", "\n%s\n" % (info.get("url") or ""), ("about", "fact"))
            if self._moby_err:
                t.insert("end", self._moby_err + "\n", ("about", "fact"))
        t.configure(state="disabled")
        t.yview_moveto(0.0)

    # ------------------------------------------------------------------ profile and shop
    def open_profile(self):
        tk = self.tk
        if self._profile_win is not None and self._profile_win.winfo_exists():
            self._profile_win.destroy()
        S2, S3, S4, S6 = T.S2, T.S3, T.S4, T.S6
        pf = self.profile
        win = self._profile_win = tk.Toplevel(self.root)
        win.title("Profile")
        win.configure(bg=T.PAGE)
        win.geometry("600x%d+%d+%d" % (500 + 84 * len(SHOP), self.root.winfo_rootx() + 280, self.root.winfo_rooty() + 10))
        win.transient(self.root)
        lab = lambda parent, text, fg=None, font=None, **kw: tk.Label(
            parent, text=text, bg=parent.cget("bg"), fg=fg or T.MUTED, font=font or (T.FONT, 9), anchor="w",
            justify="left", **kw)
        lab(win, "Level %d · %s" % (pf.level(), pf.title()), T.TEXT, (T.FONT, 18)).pack(fill="x", padx=S6, pady=(S6, 0))
        lab(win, "%d points earned · %d spent · %d to spend" % (pf.earned(), pf.spent(), pf.balance()), T.TEXT2,
            (T.MONO, 10)).pack(fill="x", padx=S6, pady=(S2, 0))
        bar = tk.Canvas(win, height=4, bg=T.RAISED, highlightthickness=0, width=552)
        bar.pack(padx=S6, pady=(S3, 0), anchor="w")
        into, span = pf.level_progress()
        bar.create_rectangle(0, 0, int(552 * into / float(span)), 4, fill=T.TEXT2, outline="")
        lab(win, "%d more points to level %d" % (level_floor(pf.level() + 1) - pf.earned(), pf.level() + 1)).pack(
            fill="x", padx=S6, pady=(S2, 0))
        lab(win, "Trophies: " + self.trophy_line(), T.TEXT2, (T.FONT, 10)).pack(fill="x", padx=S6, pady=(S4, 0))
        lab(win, "Every achievement is a trophy: bronze under 15 points, silver from 15, gold from 30. "
                 "All achievements of one game earn its platinum, worth 100 more", wraplength=552).pack(
            fill="x", padx=S6, pady=(S2, 0))
        # account: sign in to carry trophies to other computers and to appear on the leaderboard
        acc = self.account
        box = tk.Frame(win, bg=T.CARD, highlightthickness=1, highlightbackground=T.hair(T.CARD))
        box.pack(fill="x", padx=S6, pady=(S4, 0))
        btns = tk.Frame(box, bg=T.CARD)
        btns.pack(side="right", padx=S4, pady=S3)
        info = tk.Frame(box, bg=T.CARD)
        info.pack(side="left", fill="x", expand=True, padx=S4, pady=S3)
        if acc.signed_in:
            lab(info, "%s · %s" % (acc.s.get("name", ""), acc.s.get("email", "")), T.TEXT, (T.FONT, 11)).pack(fill="x")
            lab(info, self._acct_line(), T.TEXT2, wraplength=300).pack(fill="x")
            T.button(tk, btns, "Sync now", self.sync).pack(fill="x")
            T.button(tk, btns, "Leaderboard", self.open_leaderboard).pack(fill="x", pady=(S2, 0))
            row2 = tk.Frame(btns, bg=T.CARD)
            row2.pack(fill="x", pady=(S2, 0))
            T.button(tk, row2, "Sign out", self.sign_out, kind="quiet").pack(side="left")
            T.button(tk, row2, "Delete account", lambda: self.account_form("delete"), kind="quiet").pack(side="right", padx=(S3, 0))
        else:
            lab(info, "Account", T.TEXT, (T.FONT, 11)).pack(fill="x")
            lab(info, "Sign in to keep your trophies on every computer you play on, and to appear on the leaderboard",
                T.TEXT2, wraplength=300).pack(fill="x")
            T.button(tk, btns, "Sign in", lambda: self.account_form("login"), kind="primary",
                     accent=self.sel.accent).pack(fill="x")
            T.button(tk, btns, "Create account", lambda: self.account_form("create")).pack(fill="x", pady=(S2, 0))
            T.button(tk, btns, "Leaderboard", self.open_leaderboard, kind="quiet").pack(pady=(S2, 0))
        # support: one quiet row under the account, never a pop-up and never shown during play
        sup = tk.Frame(win, bg=T.PAGE)
        sup.pack(fill="x", padx=S6, pady=(S3, 0))
        T.button(tk, sup, "Support the project", lambda: webbrowser.open(SUPPORT_URL), kind="quiet").pack(side="right")
        lab(sup, "Retro Companion is free. Supporters pay for the server and the time each new game takes",
            wraplength=380).pack(side="left", fill="x", expand=True)
        lab(win, "Shop", T.TEXT, (T.FONT, 11)).pack(fill="x", padx=S6, pady=(S6, 0))
        lab(win, "Paid with trophy points only. Points come from achievements in any game", wraplength=552).pack(
            fill="x", padx=S6, pady=(2, S2))
        for item in SHOP:
            row = tk.Frame(win, bg=T.CARD, highlightthickness=1, highlightbackground=T.hair(T.CARD))
            row.pack(fill="x", padx=S6, pady=(S2, 0))
            side = tk.Frame(row, bg=T.CARD)
            side.pack(side="right", padx=S4)
            box = tk.Frame(row, bg=T.CARD)
            box.pack(side="left", fill="x", expand=True, padx=S4, pady=S3)
            lab(box, item["title"], T.TEXT, (T.FONT, 11)).pack(fill="x")
            lab(box, item["text"], T.TEXT2, wraplength=360).pack(fill="x")
            why = pf.why_not(item)
            if pf.owns(item["id"]):
                if pf.in_use(item):
                    if item["kind"] == "theme":
                        lab(side, "In use", T.TEXT2).pack()
                    else:
                        T.button(tk, side, "Switch off", lambda i=item: self.shop(i, "off")).pack()
                else:
                    T.button(tk, side, "Use", lambda i=item: self.shop(i, "use")).pack()
            elif not why:
                T.button(tk, side, "Buy · %d" % item["price"], lambda i=item: self.shop(i, "buy"), kind="primary",
                         accent=self.sel.accent).pack()
            else:
                lab(side, "%d points" % item["price"], T.TEXT2, (T.MONO, 10), ).pack(anchor="e")
                lab(side, why).pack(anchor="e")

    def shop(self, item, what):
        pf = self.profile
        if what == "buy":
            if not pf.buy(item):
                return
        else:
            pf.use(item, what == "use")
        self.store.save()
        self._unsynced = True
        self.restyle()
        self.open_profile()
        self.sync()

    # ------------------------------------------------------------------ account and sync
    def net(self, tag, *call):
        """Run an account call on a worker thread; the answer comes back through the queue."""
        def work():
            try:
                self.q.put(("net", tag, self.account.call(*call), None))
            except AccountError as exc:
                self.q.put(("net", tag, None, exc))
            except Exception as exc:
                self.q.put(("net", tag, None, AccountError("Something went wrong (%s)" % exc)))
        threading.Thread(target=work, daemon=True).start()

    def _acct_line(self):
        a = self.account.s
        if self._sync_busy:
            return "Syncing"
        if a.get("sync_error"):
            return a["sync_error"]
        if not a.get("last_sync"):
            return "Not synced yet"
        return "%sSynced %s" % ("Rank %d · " % a["rank"] if a.get("rank") else "", fmt_when(a["last_sync"]))

    def sync(self):
        """Send this computer's trophies and progress, take back what other computers earned."""
        if not self.account.signed_in or self._sync_busy:
            return
        self._sync_busy = True
        self._last_sync = time.time()
        self.net("sync", "POST", "/api/sync", {"state": json.loads(json.dumps(snapshot(self.store.data)))})

    def on_net(self, tag, res, err):
        if tag == "sync":
            self._sync_busy = False
            a = self.account.s
            if err is not None:
                if err.status == 401:
                    self.account.forget()
                    self.say("You were signed out: %s" % err, error=True)
                else:
                    a["sync_error"] = "Not synced: %s" % err
            else:
                a.pop("sync_error", None)
                for gid, g in (res["state"].get("games") or {}).items():
                    merge_into(self.store.game(gid), g)
                merge_into(self.store.data["profile"], res["state"].get("profile") or {})
                for pr in self.progress.values():
                    pr.reload()
                a["rank"], a["last_sync"], a["name"] = res.get("rank"), time.time(), res["user"]["name"]
                self._unsynced = False
                self.store.save()
                if self.profile.theme() != self._theme or (self.overlay and self.overlay.modules != self.profile.modules()):
                    self.restyle()
            self.refresh(force=True)
            if self._profile_win is not None and self._profile_win.winfo_exists():
                self.open_profile()
        elif tag == "board":
            self.fill_leaderboard(res, err)
        elif tag in ("auth", "code", "delete"):
            f = self._form
            if f is None or not f["win"].winfo_exists():
                return
            if err is not None:
                f["msg"].configure(text=str(err), fg=T.NEG)
                return
            if tag == "code":                       # the reset code is on its way: ask for it
                email = f["vars"]["email"].get().strip()
                self.account_form("code", email=email)
                return
            if tag == "delete":
                self.account.forget()
            else:
                self.account.keep(res)
            self.store.save()
            f["win"].destroy()
            self._form = None
            self.refresh(force=True)
            self.open_profile()
            self.sync()

    def sign_out(self):
        if self.account.signed_in:
            self.net("logout", "POST", "/api/logout", {})
        self.account.forget()
        self.store.save()
        self.refresh(force=True)
        self.open_profile()

    def account_form(self, mode, email=""):
        """One small window for: login, create, forgot (ask for a reset code), code (use it), delete."""
        tk = self.tk
        if self._form is not None and self._form["win"].winfo_exists():
            self._form["win"].destroy()
        S2, S3, S6 = T.S2, T.S3, T.S6
        spec = {
            "login": ("Sign in", (("email", "Email address"), ("password", "Password")), "Sign in", ""),
            "create": ("Create account", (("name", "Player name, shown on the leaderboard"), ("email", "Email address"),
                                          ("password", "Password, at least 8 characters")), "Create account",
                       "Your email address is used only to sign in and to reset your password. Your player name, "
                       "points and trophies appear on the public leaderboard. You can delete the account at any time. "
                       "Details: retro.dieergames.hu/privacy"),
            "forgot": ("Forgot the password", (("email", "Email address"),), "Send code",
                       "A six-digit code is sent to this address, if it has an account"),
            "code": ("Choose a new password", (("code", "Code from the email"), ("password", "New password, at least 8 characters")),
                     "Set password", "The code was sent to %s and works for 30 minutes" % email),
            "delete": ("Delete account", (("password", "Password"),), "Delete account",
                       "This removes the account and everything stored for it on the server. "
                       "What is on this computer stays"),
        }[mode]
        title, fields, action, note = spec
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg=T.PAGE)
        win.transient(self.root)
        win.geometry("+%d+%d" % (self.root.winfo_rootx() + 360, self.root.winfo_rooty() + 120))
        lab = lambda text, fg=None, font=None, **kw: tk.Label(win, text=text, bg=T.PAGE, fg=fg or T.MUTED,
                                                              font=font or (T.FONT, 9), anchor="w", justify="left", **kw)
        lab(title, T.TEXT, (T.FONT, 14)).pack(fill="x", padx=S6, pady=(S6, 0))
        if note:
            lab(note, wraplength=360).pack(fill="x", padx=S6, pady=(S2, 0))
        vars_ = {"email": tk.StringVar(value=email)}
        first = None
        for key, label in fields:
            lab(label).pack(fill="x", padx=S6, pady=(S3, 2))
            v = vars_[key] = tk.StringVar(value=email if key == "email" else "")
            ent = tk.Entry(win, textvariable=v, show="•" if key == "password" else "", width=44, bg=T.RAISED, fg=T.TEXT,
                           insertbackground=T.TEXT, relief="flat", font=(T.FONT, 10), highlightthickness=1,
                           highlightbackground=T.hair(T.RAISED), highlightcolor=T.MUTED)
            ent.pack(fill="x", padx=S6, ipady=6)
            first = first or ent
        msg = lab("", wraplength=360)
        msg.pack(fill="x", padx=S6, pady=(S3, 0))

        def submit():
            d = {k: v.get() if k == "password" else v.get().strip() for k, v in vars_.items()}
            msg.configure(text="Working", fg=T.MUTED)
            if mode == "login":
                self.net("auth", "POST", "/api/login", {"email": d["email"], "password": d["password"]})
            elif mode == "create":
                self.net("auth", "POST", "/api/register", {"email": d["email"], "password": d["password"], "name": d["name"]})
            elif mode == "forgot":
                self.net("code", "POST", "/api/reset/request", {"email": d["email"]})
            elif mode == "code":
                self.net("auth", "POST", "/api/reset/confirm", {"email": d["email"], "code": d["code"], "password": d["password"]})
            else:
                self.net("delete", "POST", "/api/account/delete", {"password": d["password"]})

        bar = tk.Frame(win, bg=T.PAGE)
        bar.pack(fill="x", padx=S6, pady=S6)
        T.button(tk, bar, action, submit, kind="primary", accent=self.sel.accent).pack(side="right")
        T.button(tk, bar, "Cancel", win.destroy).pack(side="right", padx=(0, S2))
        if mode == "login":
            T.button(tk, bar, "Forgot the password", lambda: self.account_form("forgot", vars_["email"].get().strip()),
                     kind="quiet").pack(side="left")
        win.bind("<Return>", lambda e: submit())
        if first is not None:
            first.focus_set()
        self._form = {"win": win, "msg": msg, "vars": vars_, "mode": mode, "submit": submit}

    def open_leaderboard(self):
        tk = self.tk
        if self._board is not None and self._board["win"].winfo_exists():
            self._board["win"].destroy()
        win = tk.Toplevel(self.root)
        win.title("Leaderboard")
        win.configure(bg=T.PAGE)
        win.geometry("620x520+%d+%d" % (self.root.winfo_rootx() + 300, self.root.winfo_rooty() + 80))
        win.transient(self.root)
        tk.Label(win, text="Leaderboard", bg=T.PAGE, fg=T.TEXT, font=(T.FONT, 14), anchor="w").pack(
            fill="x", padx=T.S6, pady=(T.S6, 0))
        sub = tk.Label(win, text="Asking the server", bg=T.PAGE, fg=T.MUTED, font=(T.FONT, 9), anchor="w", justify="left",
                       wraplength=560)
        sub.pack(fill="x", padx=T.S6, pady=(T.S2, T.S3))
        text = tk.Text(win, bg=T.PAGE, fg=T.TEXT, bd=0, highlightthickness=0, wrap="none", cursor="arrow",
                       font=(T.FONT, 10), spacing1=4, spacing3=4, tabs=("36", "right", "52", "left", "230", "left", "420", "right"),
                       selectbackground=T.RAISED, selectforeground=T.TEXT, state="disabled")
        text.pack(fill="both", expand=True, padx=T.S6, pady=(0, T.S6))
        text.tag_configure("num", foreground=T.MUTED, font=(T.MONO, 10))
        text.tag_configure("dim", foreground=T.TEXT2)
        text.tag_configure("me", foreground=T.accent_text(self.sel.accent))
        self._board = {"win": win, "sub": sub, "text": text}
        self.net("board", "GET", "/api/leaderboard?limit=50")

    def fill_leaderboard(self, res, err):
        b = self._board
        if b is None or not b["win"].winfo_exists():
            return
        if err is not None:
            b["sub"].configure(text=str(err), fg=T.NEG)
            return
        players = res.get("players") or []
        b["sub"].configure(fg=T.MUTED, text=("%d players with trophies. Points come from achievements; the server counts "
                                             "them from what each player has unlocked" % res.get("total", len(players)))
                           if players else "Nobody is on the board yet. Sign in and earn a trophy to be the first")
        t, me = b["text"], self.account.s.get("name") if self.account.signed_in else None
        t.configure(state="normal")
        t.delete("1.0", "end")
        for p in players:
            mine = ("me",) if p["name"] == me and p.get("rank") == self.account.s.get("rank") else ()
            tr = p.get("trophies") or {}
            t.insert("end", "\t%d" % p["rank"], ("num",) + mine)
            t.insert("end", "\t%s" % p["name"], mine)
            t.insert("end", "\tLevel %d · %s" % (p.get("level", 1), p.get("title", "")), ("dim",))
            t.insert("end", "\t%s\n" % "{:,}".format(p["points"]), ("num",) + mine)
            t.insert("end", "\t\t%s\n" % (" · ".join("%d %s" % (tr[g], g) for g in reversed(GRADES) if tr.get(g)) or "no trophies"),
                     ("dim",))
        t.configure(state="disabled")

    def restyle(self):
        """Rebuild every window with the theme and modules now in use."""
        pid = self.overlay_pid
        if self.overlay:
            self.overlay.close()
            self.overlay = self.overlay_pid = None
        self._theme = self.profile.theme()
        T.apply(self._theme)
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=T.PAGE)
        self._sig = self._banner_key = self._shown_cur = None
        self.build()
        self.select(self.sel)
        if pid:
            self.open_overlay(pid)

    def fill_achievements(self):
        """Same margin layout as the walkthrough: mark, points in mono, title; text below."""
        t, ach = self.text, self.ach[self.sel.id]
        top = t.yview()[0]
        t.configure(state="normal")
        t.delete("1.0", "end")
        last = None
        for a in ach.items:
            if a["group"] != last:
                last = a["group"]
                got = sum(1 for x in ach.items if x["group"] == last and x["id"] in ach.unlocked)
                t.insert("end", "%s  ·  %d of %d\n" % (last, got, sum(1 for x in ach.items if x["group"] == last)), "ch")
            when = ach.unlocked.get(a["id"])
            hidden = a.get("secret") and not when
            t.insert("end", "✓" if when else "", ("head", "mark"))
            t.insert("end", "\t%d" % a["points"], ("head", "num") + (("cur",) if when else ()))
            t.insert("end", "\t" + ("Hidden achievement" if hidden else a["title"]), ("head",) + (() if when else ("done",)))
            prog = ach.progress.get(a["id"])
            if when:
                t.insert("end", "    %s · %s" % (grade(a["points"]), time.strftime("%Y-%m-%d", time.localtime(when))),
                         ("head", "here"))
            elif prog and not hidden:
                t.insert("end", "    %s · %s / %s" % (grade(a["points"]), "{:,}".format(prog[0]), "{:,}".format(prog[1])),
                         ("head", "here"))
            else:
                t.insert("end", "    " + grade(a["points"]), ("head", "here"))
            t.insert("end", "\n", "head")
            t.insert("end", ("Keep playing to find it" if hidden else a["text"]) + "\n", "line")
        t.configure(state="disabled")
        t.yview_moveto(top)

    def fill_walkthrough(self):
        t, p, pr = self.text, self.sel, self.progress[self.sel.id]
        top = t.yview()[0]
        t.configure(state="normal")
        t.delete("1.0", "end")
        cur, last_ch = pr.current(), None
        for i, s in enumerate(p.steps):
            if s.get("ch") != last_ch:
                last_ch = s.get("ch")
                t.insert("end", (last_ch or "") + "\n", "ch")
            d = pr.is_done(i)
            here = i == cur and not d
            tag = "s%d" % i
            t.insert("end", "✓" if d else "", ("head", "mark", tag))
            t.insert("end", "\t%d" % (i + 1), ("head", "num", tag) + (("cur",) if here else ()))
            t.insert("end", "\t" + s["title"], ("head", tag) + (("done",) if d else ()))
            if here:
                t.insert("end", "    current step", ("head", "here", tag))
            t.insert("end", "\n", ("head", tag))
            if i == cur:
                t.mark_set("current_step", "end-2l")
            if i == cur or not d:
                for ln in s["lines"]:
                    t.insert("end", ln + "\n", ("line", tag))
            t.tag_bind(tag, "<Button-1>", lambda e, i=i: self.toggle_step(i))
        t.configure(state="disabled")
        if getattr(self, "_shown_cur", None) != (p.id, cur):      # new game page or new current step
            self._shown_cur = (p.id, cur)
            t.yview("current_step linestart -2l" if cur > 1 else "1.0")
        else:
            t.yview_moveto(top)

    def toggle_step(self, i):
        self.progress[self.sel.id].toggle(i)
        self.refresh(force=True)
        if self.overlay:
            self.overlay.render(force=True)

    def reset_progress(self):
        b = self.reset_btn
        if b.cget("text") != "Click again to reset":
            b._fg = T.NEG
            b.configure(text="Click again to reset", fg=T.NEG)
            self.root.after(3000, self._reset_idle)
            return
        self.progress[self.sel.id].reset()
        self._reset_idle()
        self.refresh(force=True)

    def _reset_idle(self):
        self.reset_btn._fg = T.MUTED
        self.reset_btn.configure(text="Reset progress", fg=T.MUTED)

    # ------------------------------------------------------------------ actions
    def say(self, text, error=False):
        self.message = ("!" if error else "") + text
        self.refresh(force=True)

    def choose_rom(self):
        from tkinter import filedialog
        p = self.sel
        types = [("%s ROM" % p.system, " ".join("*" + e for e in p.rom_exts) or "*"), ("All files", "*")]
        path = filedialog.askopenfilename(parent=self.root, title="Choose the ROM for " + p.title, filetypes=types)
        if path:
            self.store.game(p.id)["rom"] = path
            self.store.save()
            err = self.prepare_game(p, path)
            self.say(err, error=True) if err else self.say("")
            if err:
                return None
        return path

    def prepare_game(self, p, path):
        """Let a plugin read its tables from the player's ROM. '' or an error message."""
        if not p.data_status():
            return ""
        try:
            err = p.prepare(path)
        except Exception as exc:                 # a plugin bug must not take the library down
            err = "Could not read the game's tables (%s)" % exc
        if not err:
            self._banner_key = None
            self.draw_banner()
            if self.overlay and self.overlay_pid == p.id:
                self.overlay.render(force=True)
        return err

    def play(self):
        p = self.sel
        if self.live_pid == p.id:
            return self.say("%s is already running." % p.title)
        exe = self.store.settings.get("retroarch") or ra.find_install()
        if not exe or not os.path.isfile(exe):
            self.open_settings()
            return self.say("RetroArch was not found. Set its location in Settings.", error=True)
        rom = self.store.game(p.id).get("rom")
        if not rom or not os.path.isfile(rom):
            rom = self.choose_rom()
            if not rom:
                return
        name, core = ra.find_core(exe, p.cores)
        if not core:
            return self.say("No suitable core is installed (%s). In RetroArch: Online Updater > Core Downloader."
                            % ", ".join(p.cores), error=True)
        try:
            ra.launch(exe, core, rom, self.port)
        except OSError as exc:
            return self.say("Could not start RetroArch: %s" % exc, error=True)
        self.store.settings["retroarch"] = exe
        self.store.save()
        self.forced, self.dismissed = p.id, None
        self.say("Starting RetroArch with the %s core…" % name)

    def toggle_overlay(self):
        p = self.sel
        if self.overlay_pid == p.id:
            self.overlay.action("quit")
            return
        self.forced, self.dismissed = p.id, None
        self.open_overlay(p.id)
        self.refresh(force=True)

    def open_overlay(self, pid):
        if self.overlay:
            self.overlay.close()
        p = self.by_id[pid]
        ui = self.store.game(pid).setdefault("ui", {})
        self.overlay = Overlay(self.tk, self.root, p, self.progress[pid], ui, self.mark_dirty, self.overlay_closed,
                               ach=self.ach[pid], modules=self.profile.modules(),
                               log=self.store.game(pid).setdefault("log", []))
        self.overlay_pid = pid

    def overlay_closed(self):
        self.dismissed = self.overlay_pid
        if self.forced == self.overlay_pid:
            self.forced = None
        self.overlay = self.overlay_pid = None
        self.refresh(force=True)

    def open_settings(self):
        tk = self.tk
        if getattr(self, "_settings", None) and self._settings.winfo_exists():
            self._settings.lift()
            return
        S2, S4, S6 = T.S2, T.S4, T.S6
        win = self._settings = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=T.PAGE)
        win.geometry("640x470")
        win.transient(self.root)
        win.lift()
        s = self.store.settings
        exe = tk.StringVar(value=s.get("retroarch") or ra.find_install())
        auto = tk.BooleanVar(value=s.get("auto_overlay", True))
        lab = lambda text, fg=T.MUTED, **kw: tk.Label(win, text=text, bg=T.PAGE, fg=fg, font=(T.FONT, 9), anchor="w",
                                                      justify="left", **kw)
        lab("RetroArch program").pack(fill="x", padx=S6, pady=(S6, S2))
        row = tk.Frame(win, bg=T.PAGE)
        row.pack(fill="x", padx=S6)
        ent = tk.Entry(row, textvariable=exe, bg=T.RAISED, fg=T.TEXT, insertbackground=T.TEXT, relief="flat",
                       font=(T.MONO, 10), highlightthickness=1, highlightbackground=T.hair(T.RAISED),
                       highlightcolor=T.MUTED)
        ent.pack(side="left", fill="x", expand=True, ipady=6)
        info = lab("", wraplength=590)

        def check():
            e = exe.get().strip()
            if not e or not os.path.isfile(e):
                info.configure(text="Not found. Browse to retroarch.exe (or the RetroArch program on your system)", fg=T.NEG)
                return
            cfg = ra.config_path(e)
            val = ra.config_value(e, "network_cmd_enable")
            port = ra.config_value(e, "network_cmd_port")
            net = {"true": "on", "false": "off"}.get(val, "unknown")
            cores = [n for n in sorted({c for p in self.plugins for c in p.cores}) if ra.find_core(e, (n,))[1]]
            info.configure(fg=T.TEXT2, text="Config file: %s\nNetwork Commands: %s%s. Games started with Play get them "
                           "switched on for that session\nInstalled cores your games can use: %s" % (
                               cfg or "not found", net, ", port " + port if port else "", ", ".join(cores) or "none found"))

        def browse():
            from tkinter import filedialog
            path = filedialog.askopenfilename(parent=win, title="Locate RetroArch")
            if path:
                exe.set(path)
                check()

        T.button(tk, row, "Browse", browse).pack(side="left", padx=(S2, 0))
        T.button(tk, row, "Detect", lambda: (exe.set(ra.find_install()), check())).pack(side="left", padx=(S2, 0))
        info.pack(fill="x", padx=S6, pady=(T.S3, 0))
        tk.Checkbutton(win, text="Open the overlay when a supported game is running", variable=auto,
                       bg=T.PAGE, fg=T.TEXT, selectcolor=T.RAISED, activebackground=T.PAGE, activeforeground=T.TEXT,
                       font=(T.FONT, 10), anchor="w", bd=0, highlightthickness=0).pack(fill="x", padx=S6 - 4, pady=(S6, 0))
        lab("MobyGames API key").pack(fill="x", padx=S6, pady=(S6, S2))
        mkey = tk.StringVar(value=s.get("moby_key", ""))
        tk.Entry(win, textvariable=mkey, show="•", bg=T.RAISED, fg=T.TEXT, insertbackground=T.TEXT, relief="flat",
                 font=(T.MONO, 10), highlightthickness=1, highlightbackground=T.hair(T.RAISED),
                 highlightcolor=T.MUTED).pack(fill="x", padx=S6, ipady=6)
        lab("Optional. Fills the About tab of a game with information from MobyGames. The key is on your MobyGames "
            "API page; it is kept in the settings file on this computer and sent only to MobyGames",
            wraplength=590).pack(fill="x", padx=S6, pady=(S2, 0))
        from games import USER_DIR
        lab("Extra game plugins are loaded from %s" % USER_DIR, wraplength=590).pack(fill="x", padx=S6, pady=(S4, 0))
        if self.plugin_errors:
            lab("Plugins that failed to load: " + "; ".join(self.plugin_errors), fg=T.NEG, wraplength=590).pack(
                fill="x", padx=S6, pady=(S2, 0))

        def save():
            s["retroarch"] = exe.get().strip()
            s["auto_overlay"] = bool(auto.get())
            s["moby_key"] = mkey.get().strip()
            self.store.save()
            win.destroy()
            if self.tab == "about":
                self.load_moby()
                self.refresh(force=True)

        bar = tk.Frame(win, bg=T.PAGE)
        bar.pack(side="bottom", fill="x", padx=S6, pady=S6)
        T.button(tk, bar, "Save", save, kind="primary", accent=self.sel.accent).pack(side="right")
        T.button(tk, bar, "Cancel", win.destroy).pack(side="right", padx=(0, S2))
        check()

    # ------------------------------------------------------------------ polling
    def net_loop(self):
        conn = ra.RetroArch(self.host, self.port)
        last = None
        while not self.stop.is_set():
            st = conn.status()
            content = (st["name"], st["crc"]) if st and st["state"] != "CONTENTLESS" else None
            if content != last:
                conn.bad.clear()
                conn.cmd = "READ_CORE_MEMORY"
                last = content
            plugin = next((p for p in self.plugins if p.matches(st)), None) if content else None
            if plugin is None and self.forced and (st is None or content):
                plugin = self.by_id.get(self.forced)
            if plugin is not None:
                blocks, err = conn.read_blocks(plugin.memory)
                self.q.put(("frame", st, plugin.id, blocks, err))
                delay = plugin.poll_seconds
            else:
                self.q.put(("frame", st, None, None, None))
                delay = 1.0
            self.stop.wait(delay)

    def on_frame(self, st, pid, blocks, err):
        now = time.time()
        self.status = st
        if pid is None:
            self.live_pid, self.live_conn, self.dismissed = None, "offline", None
            if self.overlay:
                self.overlay.update("offline", None)
            return
        p = self.by_id[pid]
        state = None
        if blocks is None:
            conn = "offline" if st is None else "nocore"
        else:
            try:
                state = p.parse(blocks)
            except Exception:
                state = None
            conn = "live" if state is not None else "nostate"
        self.live_pid = pid if (st is not None or blocks is not None) else None
        self.live_conn = conn
        if state is not None:
            gs = self.store.game(pid)
            log = gs.setdefault("log", [])              # what happened, for the overlay's log module
            pr = self.progress[pid]
            was = [pr.is_done(i) for i in range(len(p.steps))]
            pr.observe(state)
            for i, s in enumerate(p.steps):
                if not was[i] and pr.is_done(i):
                    log.append([now, "Step %d done: %s" % (i + 1, s["title"])])
            try:
                for text in p.events(state, self._prev.get(pid)) or ():
                    log.append([now, str(text)])
            except Exception:                           # a plugin bug must not stop the polling
                pass
            self._prev[pid] = state
            dt = min(2.0, max(0.0, now - self.last_frame)) if st is None or st["state"] == "PLAYING" else 0.0
            gs["playtime"] = gs.get("playtime", 0) + dt
            ach = self.ach[pid]
            self._unsynced = True
            for a in ach.observe(state, dt):
                log.append([now, "Achievement: %s (+%d points)" % (a["title"], a["points"])])
                self.root.after(500, self.sync)        # a new trophy goes to the server right away
                if self.overlay and self.overlay_pid == pid:
                    self.overlay.toast(a, ach.count(), len(ach.items))
                if self.sel.id == pid:
                    self.say("Achievement unlocked: %s (+%d points)" % (a["title"], a["points"]))
            del log[:-LOG_KEEP]                         # in place: the overlay holds this very list
            gs["last_played"] = now
            gs["summary"] = p.summary(state)
            self.dirty = True
        self.last_frame = now
        if (self.overlay is None and conn in ("live", "nostate") and self.dismissed != pid
                and self.store.settings.get("auto_overlay", True)):
            self.open_overlay(pid)
        if self.overlay and self.overlay_pid == pid:
            self.overlay.update(conn, state, err or "")

    def mark_dirty(self):
        self.dirty = True

    def tick(self):
        try:
            while True:
                ev = self.q.get_nowait()
                if ev[0] == "key" and self.overlay:
                    self.overlay.action(ev[1])
                elif ev[0] == "frame":
                    self.on_frame(*ev[1:])
                elif ev[0] == "moby":
                    self.on_moby(*ev[1:])
                elif ev[0] == "net":
                    self.on_net(*ev[1:])
        except queue.Empty:
            pass
        self.refresh()
        if self.dirty and time.time() - self.last_save > 15:
            self.store.save()
            self.dirty, self.last_save = False, time.time()
        if self._unsynced and time.time() - self._last_sync > 300:
            self.sync()                              # at most every five minutes while playing
        if not self.stop.is_set():
            self.root.after(150, self.tick)

    def quit(self):
        self.stop.set()
        self.store.save()
        if self.account.signed_in and self._unsynced and not self._sync_busy:
            try:                                     # one last short try; the next start syncs anyway
                self.account.call("POST", "/api/sync", {"state": snapshot(self.store.data)}, timeout=4)
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    App().run()
