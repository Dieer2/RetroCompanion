"""Game plugins. Built-in ones are listed here; extra ones are picked up from the user's
plugin folder (~/RetroCompanion/games/*.py), so a new game is one dropped-in file."""
import importlib.util
import os
import sys

USER_DIR = os.path.join(os.path.expanduser("~"), "RetroCompanion", "games")


def load_plugins():
    from . import dragon_warrior
    plugins, errors = [dragon_warrior.PLUGIN], []
    if os.path.isdir(USER_DIR):
        for fn in sorted(os.listdir(USER_DIR)):
            if not fn.endswith(".py") or fn.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location("rc_user_" + fn[:-3], os.path.join(USER_DIR, fn))
                mod = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = mod
                spec.loader.exec_module(mod)
                p = mod.PLUGIN
                if any(p.id == q.id for q in plugins):
                    raise ValueError("duplicate plugin id %r" % p.id)
                plugins.append(p)
            except Exception as exc:          # a broken plugin must not take the app down
                errors.append("%s: %s" % (fn, exc))
    return plugins, errors
