"""The contract between the platform and a game.

A game is one Python module that defines PLUGIN = <GamePlugin subclass>(). The platform
handles everything that is the same for every game (finding and launching RetroArch,
detecting the running game, polling memory, the overlay window, drawing maps, progress,
play time, the library). The plugin only answers game questions:

    memory      which address ranges to read each tick
    parse()     turn those bytes into a state object (or None on title screens)
    steps       the walkthrough
    step_done() is a step finished, judging by the state
    view()      what the overlay should show for a state

See games/dragon_warrior.py for a complete example and README.md for the field list.
"""
import re


class GamePlugin:
    id = ""               # unique, file-name safe
    title = ""
    system = ""           # shown in the library, e.g. "NES"
    year = None
    publisher = ""
    blurb = ""            # one or two sentences for the game page
    accent = "#f2c14e"
    cores = ()            # libretro core names, best first, e.g. ("mesen", "fceumm")
    rom_exts = ()         # e.g. (".nes",)
    crc32 = ()            # content CRCs as RetroArch reports them (lowercase hex)
    name_pattern = ""     # regex matched against the lowercase content name
    moby_id = None        # MobyGames game id, if known; otherwise the title is searched
    memory = ()           # (address, length, required) read every tick
    poll_seconds = 0.4
    steps = ()            # dicts: id, ch (chapter), title, lines; optional: rec, optional, soft, anchor

    # -- data from the player's own copy -------------------------------------------
    def data_status(self):
        """'' when the plugin has all it needs, else one sentence telling the player what to do.
        A plugin that reads tables from the player's ROM (instead of shipping them) says here
        that the ROM still has to be chosen."""
        return ""

    def prepare(self, path):
        """Read what the plugin needs from the player's ROM at `path`. '' or an error message."""
        return ""

    # -- detection ---------------------------------------------------------------
    def matches(self, status):
        if status.get("crc") and status["crc"] in self.crc32:
            return True
        return bool(self.name_pattern and re.search(self.name_pattern, status.get("name", "").lower()))

    # -- state -------------------------------------------------------------------
    def parse(self, blocks):
        """blocks: list of bytes (or None for optional ranges that failed). Return a state or None."""
        raise NotImplementedError

    def is_fresh_start(self, state):
        """True on a brand-new game, so old progress can be cleared."""
        return False

    def observe(self, state, seen):
        """Record durable facts the memory itself forgets (e.g. places visited) into the `seen` set."""

    def step_done(self, step, state, seen):
        return False

    def summary(self, state):
        """One line for the library, e.g. 'Lv 7 · Kol'."""
        return ""

    # -- achievements ------------------------------------------------------------
    achievements = ()     # dicts: id, group, title, text, points; optional: secret (hidden until unlocked)

    def track(self, state, prev, memo, dt):
        """Called for every live state, before achieved(). prev is the state before it (None
        on the first one), memo a dict kept in the store (JSON types only), dt the seconds
        of play since prev. Record here what memory itself forgets: counts, places, and
        things that are only true for a moment."""

    def achieved(self, ach, state, memo):
        """True/False, or (current, total) for a counted achievement."""
        return False

    def events(self, state, prev):
        """Short lines for the overlay's log about what changed between prev and state
        (an enemy beaten, a level gained, an item found). prev is None on the first state."""
        return ()

    # -- presentation ------------------------------------------------------------
    def view(self, state, ctx):
        """Return a dict; every key is optional:
             location  str            header line
             stats     str            main stat line
             gear      str            secondary line
             self      [str]          'my stats' panel
             battle    {title, frac, lines}
             nav       [str]          directions for the shown step
             warn      [str]
             notes     [str]          notes about the current place
             map       map spec, see companion/overlay.py MapView
             short     {stats, nav}   one short line each, for the compact modules (optional;
                                      battle may carry its own "short")
           ctx.step is the step being shown, ctx.zoom the map zoom toggle. state may be None
           (no connection): then return whatever static help makes sense."""
        return {}

    def banner(self):
        """Optional backdrop for the game page: dict(rows=[str], palette={char: color}, y0, h)."""
        return None


class Progress:
    """Walkthrough progress for one game. Works with or without a live state."""

    def __init__(self, plugin, gstate, save):
        self.p = plugin
        self.g = gstate
        self._save = save
        self.manual = set(gstate.get("manual", []))
        self.seen = set(gstate.get("seen", []))
        self.auto = set(gstate.get("done", []))      # last known automatically detected steps

    def reload(self):
        """Take the sets from the store again (after a sync merged another computer's data in)."""
        self.manual = set(self.g.get("manual", []))
        self.seen = set(self.g.get("seen", []))
        self.auto = set(self.g.get("done", []))

    def save(self):
        self.g["manual"] = sorted(self.manual)
        self.g["seen"] = sorted(self.seen, key=str)
        self.g["done"] = sorted(self.auto)
        self._save()

    def reset(self):
        self.manual.clear()
        self.seen.clear()
        self.auto.clear()
        self.save()

    def observe(self, state):
        before = (len(self.seen), frozenset(self.auto))
        if self.p.is_fresh_start(state) and (self.manual or len(self.seen) > 1):
            self.manual.clear()
            self.seen.clear()
            before = None
        self.p.observe(state, self.seen)
        self.auto = {s["id"] for s in self.p.steps if self.p.step_done(s, state, self.seen)}
        if before != (len(self.seen), frozenset(self.auto)):
            self.save()
            return True
        return False

    def is_done(self, i, state=None):
        sid = self.p.steps[i]["id"]
        return sid in self.manual or sid in self.auto

    def done_count(self):
        return sum(1 for i in range(len(self.p.steps)) if self.is_done(i))

    def current(self):
        """First step not done. Soft steps (training, shopping, visits) never drag you back
        behind a later story step that is already finished."""
        steps = self.p.steps
        done = [self.is_done(i) for i in range(len(steps))]
        last = max([i for i, d in enumerate(done) if d and steps[i].get("anchor", True)] or [-1])
        for i, d in enumerate(done):
            if d or (steps[i].get("soft") and i < last):
                continue
            return i
        return len(steps) - 1

    def toggle(self, i):
        sid = self.p.steps[i]["id"]
        if sid in self.manual:
            self.manual.discard(sid)
        elif sid in self.auto:
            return
        else:
            self.manual.add(sid)
        self.save()
