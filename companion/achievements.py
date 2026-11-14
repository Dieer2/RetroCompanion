"""Achievements, the same machinery for every game.

A plugin lists its achievements and answers two questions (see GamePlugin):

    track(state, prev, memo, dt)    note what memory forgets: kills, deaths, places, and
                                    things that are only true for a moment
    achieved(ach, state, memo)      True / False, or (current, total) for counted ones

This module keeps what is unlocked (with the time), the plugin's memo and the last known
progress of counted achievements in the game's entry of the store. An achievement stays
unlocked for good: starting a new game or resetting the walkthrough does not take it away.
"""
import time


class Achievements:
    def __init__(self, plugin, gstate, save):
        self.p = plugin
        self.g = gstate
        self._save = save
        self.unlocked = gstate.setdefault("ach", {})            # id -> unix time
        self.memo = gstate.setdefault("ach_memo", {})           # the plugin's own notes
        self.progress = gstate.setdefault("ach_progress", {})   # id -> [current, total]
        self.prev = None
        self.error = ""

    @property
    def items(self):
        return self.p.achievements

    def count(self):
        return sum(1 for a in self.items if a["id"] in self.unlocked)

    def points(self):
        return sum(a["points"] for a in self.items if a["id"] in self.unlocked)

    def total_points(self):
        return sum(a["points"] for a in self.items)

    def signature(self):
        """Changes whenever something the library shows about achievements changes."""
        return (len(self.unlocked), tuple(sorted((k, v[0]) for k, v in self.progress.items())))

    def observe(self, state, dt=0.0):
        """Feed one live state. Returns the achievements unlocked by it, in list order."""
        try:
            self.p.track(state, self.prev, self.memo, dt)
        except Exception as exc:                # a plugin bug must not stop the polling
            self.error = "track: %s" % exc
        self.prev = state
        new = []
        for a in self.items:
            try:
                r = self.p.achieved(a, state, self.memo)
            except Exception as exc:
                self.error = "%s: %s" % (a["id"], exc)
                continue
            if isinstance(r, tuple):
                cur, total = min(int(r[0]), int(r[1])), int(r[1])
                if self.progress.get(a["id"]) != [cur, total]:
                    self.progress[a["id"]] = [cur, total]
                r = cur >= total
            if r and a["id"] not in self.unlocked:
                self.unlocked[a["id"]] = time.time()
                new.append(a)
        if new:
            self._save()
        return new
