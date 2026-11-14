"""Settings and per-game data, kept in one JSON file in the user's home folder."""
import json
import os

PATH = os.path.join(os.path.expanduser("~"), ".retro_companion.json")
LEGACY_DW = os.path.join(os.path.expanduser("~"), ".dw_overlay_state.json")


class Store:
    def __init__(self, path=PATH):
        self.path = path
        self.data = {"settings": {}, "games": {}, "profile": {}}
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                self.data["settings"] = d.get("settings", {})
                self.data["games"] = d.get("games", {})
                self.data["profile"] = d.get("profile", {})
        except (OSError, ValueError):
            self._import_legacy()

    def _import_legacy(self):
        """Carry over progress from the single-game overlay that came before this app."""
        try:
            with open(LEGACY_DW, encoding="utf-8") as fh:
                d = json.load(fh)
            g = self.game("dragon_warrior")
            g["manual"] = d.get("manual", [])
            g["seen"] = d.get("seen", [])
            g["ui"] = d.get("ui", {})
        except (OSError, ValueError):
            pass

    @property
    def settings(self):
        return self.data["settings"]

    def game(self, gid):
        return self.data["games"].setdefault(gid, {})

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass
