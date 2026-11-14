"""Game information from MobyGames (API v2, https://api.mobygames.com/v2).

Needs the user's own API key (a MobyGames API subscription; the Hobbyist plan is enough for
the fields used here). The key is kept in the local settings and sent only to MobyGames.
Hobbyist keys are limited to one request every five seconds, so a game is fetched once and
the result is cached in the store.

    GET /games?api_key=KEY&id=9223&include=...            a plugin that knows its MobyGames id
    GET /games?api_key=KEY&title=Dragon+Warrior&include=...   otherwise: search by title
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.mobygames.com/v2"
FIELDS = "game_id,title,moby_url,description,genres,moby_score,platforms,developers,publishers,release_date"
MAX_AGE = 30 * 86400          # refresh a cached entry after a month


class MobyError(Exception):
    pass


def plain(text, limit=900):
    """MobyGames descriptions are HTML: keep the words, cut at a sentence end."""
    text = re.sub(r"(?i)<\s*(br|/p|/li|/h\d)\s*/?>", "\n", text or "")
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()
    if len(text) > limit:
        cut = text.rfind(". ", 0, limit)
        text = text[:cut + 1] if cut > limit // 2 else text[:limit].rstrip() + "…"
    return text


def pick(games, title, system):
    """The entry meant by a plugin: same title first, then one released on its system."""
    same = [g for g in games if (g.get("title") or "").casefold() == title.casefold()]
    on = [g for g in (same or games) if any((p.get("name") or "").casefold() == system.casefold()
                                            for p in g.get("platforms") or ())]
    return (on or same or games or [None])[0]


def summarize(g, system=""):
    names = lambda key: [x.get("name") for x in g.get(key) or () if x.get("name")]
    plats = g.get("platforms") or ()
    here = next((p for p in plats if (p.get("name") or "").casefold() == system.casefold()), None)
    genres = g.get("genres") or ()
    basic = [x.get("name") for x in genres if x.get("category") == "Basic Genres"]
    other = [x.get("name") for x in genres if x.get("category") != "Basic Genres"]
    return {"id": g.get("game_id"), "title": g.get("title"), "url": g.get("moby_url"), "score": g.get("moby_score"),
            "released": (here or {}).get("release_date") or g.get("release_date"),
            "genres": [x for x in basic + other if x][:6], "developers": names("developers")[:3],
            "publishers": names("publishers")[:3], "platforms": [p.get("name") for p in plats if p.get("name")][:8],
            "description": plain(g.get("description")), "fetched": time.time()}


def fetch(key, title, system="", moby_id=None, base=BASE, timeout=20):
    """Returns the summary dict, or raises MobyError with a message fit for the message line."""
    q = {"api_key": key, "include": FIELDS}
    if moby_id:
        q["id"] = moby_id
    else:
        q.update(title=title, limit=20)
    req = urllib.request.Request(base + "/games?" + urllib.parse.urlencode(q),
                                 headers={"User-Agent": "RetroCompanion", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except urllib.error.HTTPError as exc:
        raise MobyError({401: "MobyGames did not accept the API key", 429: "MobyGames asks to slow down, try again in a minute"}
                        .get(exc.code, "MobyGames answered with error %d" % exc.code))
    except (OSError, ValueError) as exc:
        raise MobyError("MobyGames could not be reached (%s)" % getattr(exc, "reason", exc))
    games = data.get("games") or []
    g = next((x for x in games if x.get("game_id") == moby_id), None) if moby_id else pick(games, title, system)
    if g is None:
        raise MobyError("MobyGames has no game called “%s”" % title)
    return summarize(g, system)
