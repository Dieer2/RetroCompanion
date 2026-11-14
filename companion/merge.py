"""Merging two copies of a player's data (this computer's and the server's).

Used on both sides: the server merges what a client sends into what it has, the client
merges the server's answer back into its store. Nothing is ever taken away by a merge, so
two computers that played separately end up with everything both of them earned.

    dict                    key by key
    list                    union, order kept
    number                  the larger one (counters, play time, last played)
    bool                    true if either is
    text                    the incoming one, if it is not empty
    "ach" (id -> time)      the earlier time: when it was first earned
    "ach_progress"          per id, the pair that is further along
    "use"                   the incoming preferences as a whole, if there are any
"""

SYNCED_GAME_KEYS = ("ach", "ach_memo", "ach_progress", "manual", "seen", "done", "playtime", "last_played", "summary")
SYNCED_PROFILE_KEYS = ("owned", "use")


def snapshot(store_data):
    """The part of the store that follows the player from computer to computer."""
    games = {gid: {k: g[k] for k in SYNCED_GAME_KEYS if k in g} for gid, g in store_data.get("games", {}).items()}
    prof = store_data.get("profile", {})
    return {"games": games, "profile": {k: prof[k] for k in SYNCED_PROFILE_KEYS if k in prof}}


def merge_into(base, incoming, key=None):
    """Merge incoming into base in place (dicts and lists keep their identity). Returns base."""
    for k, new in incoming.items():
        old = base.get(k)
        if key == "ach":
            if isinstance(new, (int, float)) and not isinstance(new, bool):
                base[k] = min(old, new) if isinstance(old, (int, float)) and not isinstance(old, bool) else new
        elif key == "ach_progress":
            if isinstance(new, list) and len(new) == 2 and (not isinstance(old, list) or len(old) != 2 or new[0] > old[0]):
                base[k] = list(new)
        elif k == "use" and isinstance(new, dict):
            if new:
                if isinstance(old, dict):
                    old.clear()
                    old.update(new)
                else:
                    base[k] = dict(new)
        elif isinstance(new, dict):
            if not isinstance(old, dict):
                old = base[k] = {}
            merge_into(old, new, k)
        elif isinstance(new, list):
            if not isinstance(old, list):
                old = base[k] = []
            for x in new:
                if x not in old:
                    old.append(x)
        elif isinstance(new, bool):
            base[k] = bool(old) or new
        elif isinstance(new, (int, float)):
            base[k] = max(old, new) if isinstance(old, (int, float)) and not isinstance(old, bool) else new
        elif isinstance(new, str):
            if new or old is None:
                base[k] = new
    return base
