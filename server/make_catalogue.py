"""Writes catalogue.json for the server from the game plugins:  python server/make_catalogue.py [out]

The server never trusts points sent by a client; it looks them up here. Run this again and
redeploy the file whenever a game or its achievements change.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from games import load_plugins          # noqa: E402

plugins, errors = load_plugins()
cat = {"games": {p.id: {"title": p.title, "ach": {a["id"]: a["points"] for a in p.achievements}} for p in plugins}}
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "server", "catalogue.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(cat, fh, indent=1)
print("%d games, %d achievements -> %s" % (len(cat["games"]), sum(len(g["ach"]) for g in cat["games"].values()), out))
