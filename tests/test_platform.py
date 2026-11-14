"""Platform test against a simulated RetroArch:  python tests/test_platform.py

Needs the Dragon Warrior tables, which come only from a ROM: either they were read before
(the app saves them in ~/RetroCompanion/data) or set RC_DW_ROM to the path of
Dragon Warrior (USA).nes."""
import sys, os, time, tempfile, subprocess, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
from mock_ra import Mock, setram
from companion.retroarch import RetroArch
from companion.plugin import Progress
from companion.store import Store
import games.dragon_warrior as DW
P = DW.PLUGIN
if P.data_status():
    rom = os.environ.get("RC_DW_ROM")
    if not rom:
        sys.exit("The Dragon Warrior tables are not on this computer yet: set RC_DW_ROM to the ROM's path")
    err = P.prepare(rom); assert not err, err
assert DW.DATA and not P.data_status()
# the plugin itself carries nothing from the game, and works (without map or routes) before the ROM is chosen
src = open(DW.__file__, encoding="utf-8").read()
assert "DATA_B64" not in src and "b64decode" not in src
check = ("import sys; sys.path.insert(0, %r); import games.dragon_warrior as DW; P = DW.PLUGIN; "
         "assert DW.DATA is None and P.data_status() and P.banner() is None; "
         "g = DW.Game(bytes(0x110)); g.level, g.map, g.maxhp = 5, 1, 30; "
         "v = P.view(g, type('C', (), {'step': P.steps[3], 'index': 3, 'zoom': True})); "
         "assert 'map' not in v and any('choose your Dragon Warrior ROM' in w for w in v['warn']), v; "
         "bad = sys.argv[1]; open(bad, 'wb').write(b'NES\\x1a' + bytes(0x20000)); "
         "assert 'not Dragon Warrior' in P.prepare(bad) and P.data_status(); "
         "assert 'Could not read' in P.prepare(bad + '.missing'); print('no-data mode OK')") % os.path.dirname(HERE)
empty = tempfile.mkdtemp()
out = subprocess.run([sys.executable, "-c", check, os.path.join(empty, "x.nes")], env=dict(os.environ, RC_DATA_DIR=empty),
                     capture_output=True, text=True)
assert out.returncode == 0 and "no-data mode OK" in out.stdout, out.stderr
assert DW.BESTIARY == sorted({e for grp in DW.DATA["groups"] for e in grp} | {24})
print("data from the ROM OK; no-data mode OK")
m = Mock(55396); ra = RetroArch("127.0.0.1", 55396)
print("status:", ra.status())
st = Store(tempfile.mktemp()); pr = Progress(P, st.game(P.id), st.save)
def cur(**k):
    setram(m.ram, **k); blocks, err = ra.read_blocks(P.memory); assert blocks, err
    g = P.parse(blocks); pr.observe(g); return g, P.steps[pr.current()]
blocks, err = ra.read_blocks(P.memory); print("title screen parse:", P.parse(blocks))
seq = [
 (dict(map=5, x=3, y=4, level=1, hp=15, maxhp=15, keys=1, gold=120, items=[1]), "throne"),
 (dict(map=4, pflags=8, keys=0), "brecc"), (dict(map=8, equip=0x44, mods=0x10), "lv3"),
 (dict(level=3, exp=23, map=1, x=43, y=40), "tablet"), (dict(map=0x1D), None), (dict(map=1), "gear1"),
 (dict(equip=0x69, level=5), "garinham"), (dict(map=9), "gear2"), (dict(equip=0x8E, level=7, map=1), "kol"),
 (dict(map=7, x=9, y=3), "flute"), (dict(items=[1,5]), "lv10"), (dict(level=10, equip=0x92, map=1, x=104, y=20), "swamp"),
 (dict(map=0x15), "rimuldar"), (dict(map=0x0B), "keys"), (dict(keys=6), "lv13"), (dict(level=13, equip=0xB6, map=4), "stones"),
 (dict(items=[5,12], keys=3), "harp"), (dict(items=[5,12,10]), "staff"), (dict(items=[5,12,13]), "lv15"),
 (dict(level=15, map=1, x=70, y=100), "golem"), (dict(story=2), "cantshop"), (dict(equip=0xD7), "lv17"),
 (dict(level=17, map=3, x=10, y=10), "armor"), (dict(equip=0xDF, map=0x15, x=4, y=10), "princess"), (dict(pflags=9), "return"),
 (dict(pflags=10, items=[5,12,13,8], map=1, x=80, y=110), "token"), (dict(items=[12,13,8,7]), "drop"),
 (dict(items=[8,14], x=70, y=49), "bridge"), (dict(items=[8], mods=0x18|3), "lv19"), (dict(level=19, map=2, x=10, y=8), "passage"),
 (dict(mods=0x1F), "sword"), (dict(equip=0xFF, map=0x12), "dlord"), (dict(story=6, map=6), "ending")]
for k, want in seq:
    g, s = cur(**k)
    if want: assert s["id"] == want, (s["id"], want)
print("step sequence OK;", pr.done_count(), "done; summary:", P.summary(g))
class C: step=P.steps[25]; index=25; zoom=True
setram(m.ram, map=1, x=80, y=110, items=[5,12,13,8], story=2, mods=0x10, pflags=10, level=18)
g = P.parse(ra.read_blocks(P.memory)[0]); v = P.view(g, C)
print(v["location"], "|", v["nav"], "| map", v["map"]["z"], len(v["map"]["path"]))
st.save(); st2 = Store(st.path); pr2 = Progress(P, st2.game(P.id), st2.save); print("persisted:", pr2.done_count(), pr2.current())
m.mode = "ramonly"; ra2 = RetroArch("127.0.0.1", 55396); b, e = ra2.read_blocks(P.memory); print("fallback cmd:", ra2.cmd, b is not None)
print("offline:", RetroArch("127.0.0.1", 55395).status())
# cellar and shrines: 3-bit maps on the town tile set; their chests must be reachable
W = P.world
assert [W.dun[k] for k in (0x0B, 0x0C, 0x0D, 0x0E, 0x0F)] == [False, False, False, False, True]
for mp, x, y, goal in ((0x0C, 0, 4, (4, 5)), (0x0D, 4, 9, (3, 4)), (0x04, 10, 10, (4, 5))):
    setram(m.ram, map=mp, x=x, y=y, keys=2)
    g = P.parse(ra2.read_blocks(P.memory)[0]); path = W.route(g, ("tile", 0x0C if mp != 0x0D else 0x0D) + goal)
    assert path and path[-1][1:] == goal and W.tile(*path[-1]) == "3", (mp, path)
    assert P.map_spec(g, path, None, False)["palette"] is (DW.COL_TOWN)
print("cellar/shrine routes OK")
from companion.dashboard import hotkeys_wanted as hw
assert hw(True, "retroarch.exe") and hw(True, "retroarch_debug.exe")
assert not hw(False, "retroarch.exe") and not hw(True, "notepad.exe") and not hw(True, "") and not hw(True, None)
print("hotkey scope OK")
# achievements: a short life story fed tick by tick
from companion.achievements import Achievements
m.ram[:] = bytearray(0x8000)
st3 = Store(tempfile.mktemp()); AC = Achievements(P, st3.game(P.id), st3.save); EN = DW.DATA["en"]
def feed(dt=1.0, **k):
    setram(m.ram, **k); return {a["id"] for a in AC.observe(P.parse(ra2.read_blocks(P.memory)[0]), dt)}
assert feed(map=5, x=3, y=4, level=1, hp=15, maxhp=15) == set()                 # brand-new game: the run is followed
assert feed(map=4, pflags=8) == {"out"}
assert feed(map=1, en_id=0, en_hp=3, en_stats=EN[0], chr=3) == set()
assert feed(exp=1, hp=2) == {"win1", "thread"}                                 # slime down with 2 HP left
assert feed(en_id=16, en_hp=4, en_stats=EN[16], hp=15) == set()
assert feed(exp=116) == {"metal1"}                                             # metal slime: exactly +115 XP
assert feed(exp=120) == set() and AC.memo["wins"] == 2                         # +4 is not this enemy's XP: no kill
assert feed(hp=0) == {"dead"} and list(AC.memo["runs"].values())[0]["deaths"] == 1
assert feed(map=5, hp=15, gold=0) == set()                                     # revived in the throne room
assert feed(map=1, level=10, exp=2000) == {"lv10"}                             # died on the way: no "clean10"
assert feed(en_id=24, en_hp=70, en_stats=EN[24], x=73, y=100) == set()
assert feed(story=2, exp=2005) == {"golem", "noflute"}                         # no flute in the pack, none awarded
assert AC.progress["bestiary"] == [3, 38] and AC.progress["lv30"] == [10, 30]
assert feed(map=6, level=18, exp=19500) == {"maps"} - {"maps"}                 # arriving somewhere is not an event
assert feed(story=6) == {"dlord", "dl19", "nosword", "duty", "fast", "passage"}  # died once: no "clean"
assert feed(map=5, level=1, exp=0, pflags=0, story=0, x=3, y=4) == set()       # a new adventure
assert feed(map=1, pflags=8, level=10, exp=2000) == {"clean10"}
assert feed(map=6, level=20, exp=26000, pflags=9, equip=0xFF) == {"kit", "sword", "armor", "lv20", "princess", "gdragon"}
assert feed(story=4) == {"clean", "carry"} and "duty" in AC.unlocked
# a second save file (other hero name) is its own adventure: its death does not stain the first one
m.ram[0xB5:0xB9] = b"\x24\x25\x26\x27"
assert feed(map=1, story=0, level=3, exp=30, hp=9, pflags=8) == set() and feed(hp=0) == set()
assert len(AC.memo["runs"]) == 1 and list(AC.memo["runs"].values())[0]["deaths"] == 0 and "not followed" in P.run_line()
m.ram[0xB5:0xB9] = bytes(4); feed(hp=20, map=4); assert "no deaths" in P.run_line()
st3.save(); AC2 = Achievements(P, Store(st3.path).game(P.id), None)
assert AC2.count() == AC.count() == 23 and AC2.points() == AC.points(), (AC.count(), AC.points())
assert len(P.achievements) == 50 and AC.total_points() == 940 and len({a["id"] for a in P.achievements}) == 50
print("achievements OK: %d of %d, %d of %d points" % (AC.count(), len(P.achievements), AC.points(), AC.total_points()))
# profile: trophies, level, shop
from companion.profile import Profile, SHOP, grade, level_floor
assert [grade(x) for x in (5, 10, 15, 25, 30, 50)] == ["bronze", "bronze", "silver", "silver", "gold", "gold"]
assert [level_floor(n) for n in (1, 2, 3, 4, 5)] == [0, 100, 300, 600, 1000]
pd = {}; PF = Profile(pd, {P.id: AC}, lambda: None); item = {i["id"]: i for i in SHOP}
assert PF.earned() == 505 and PF.level() == 3 and PF.title() == "Adventurer" and PF.level_progress() == (205, 300)
assert sum(PF.trophies().values()) == 23 and PF.trophies()["platinum"] == 0 and PF.theme() == "warm"
assert PF.why_not(item["graphite"]) == "" and PF.buy(item["graphite"]) and PF.theme() == "graphite" and PF.balance() == 355
assert not PF.buy(item["graphite"]) and PF.buy(item["tracker"]) and PF.modules() == {"tracker"} and PF.balance() == 155
assert PF.why_not(item["paper"]) == "145 more points needed" and not PF.buy(item["paper"]) and PF.balance() == 155
PF.use(item["tracker"], False); PF.use(item["warm"]); assert PF.modules() == set() and PF.theme() == "warm"
PF2 = Profile(pd, {P.id: AC}, lambda: None); assert PF2.owns("graphite") and PF2.spent() == 350 and PF2.level() == 3
AC.unlocked.update({a["id"]: 1.0 for a in P.achievements})          # everything: platinum and its bonus
assert PF.trophies()["platinum"] == 1 and PF.earned() == 940 + 100 and PF.level() == 5
print("profile OK")
# MobyGames client against a local stand-in for api.mobygames.com/v2
import json, threading, http.server
from companion import moby
SAMPLE = {"games": [
    {"game_id": 8075, "title": "Dragon Warrior II", "platforms": [{"name": "NES", "release_date": "1987-01-26"}]},
    {"game_id": 9223, "title": "Dragon Warrior", "moby_url": "https://www.mobygames.com/game/9223/dragon-warrior/",
     "moby_score": 6.6, "release_date": "1986-05-27", "description": "<p>Once upon a time, the Balls of Light &amp; more.</p><p>Second.</p>",
     "genres": [{"category": "Setting", "name": "Fantasy"}, {"category": "Basic Genres", "name": "Role-playing (RPG)"}],
     "platforms": [{"name": "MSX", "release_date": "1986-11"}, {"name": "NES", "release_date": "1986-05-27"}],
     "developers": [{"name": "Chunsoft Co., Ltd."}], "publishers": [{"name": "Enix Corporation"}]}]}
seen_q = []
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        seen_q.append(self.path)
        ok = "api_key=good" in self.path
        body = json.dumps(SAMPLE if ok else {"error": "Authorization required"}).encode()
        self.send_response(200 if ok else 401); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % srv.server_address[1]
info = moby.fetch("good", "Dragon Warrior", "NES", base=base)
assert info["id"] == 9223 and info["released"] == "1986-05-27" and info["genres"] == ["Role-playing (RPG)", "Fantasy"]
assert info["description"] == "Once upon a time, the Balls of Light & more.\nSecond." and info["developers"] == ["Chunsoft Co., Ltd."]
assert "title=Dragon+Warrior" in seen_q[-1] and moby.fetch("good", "x", "NES", moby_id=9223, base=base) and "id=9223" in seen_q[-1]
try: moby.fetch("bad", "Dragon Warrior", "NES", base=base); raise SystemExit("401 not reported")
except moby.MobyError as exc: assert "API key" in str(exc)
srv.shutdown(); print("moby client OK")
# the account server, run in-process: register, sync from two "computers", leaderboard, reset, delete
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import subprocess, copy
import app as SRV
from companion.account import Account, AccountError
from companion.merge import merge_into, snapshot
cat_path = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "server", "make_catalogue.py"), cat_path], check=True, stdout=subprocess.DEVNULL)
mails = []
httpd, svc = SRV.build(tempfile.mktemp(suffix=".db"), cat_path, 0, lambda to, subject, text: mails.append((to, text)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
os.environ["RC_SERVER"] = "http://127.0.0.1:%d" % httpd.server_address[1]
def fails(fn, status):
    try: fn()
    except AccountError as exc: return exc.status == status
    return False
pc1, pc2 = Account({}), Account({})
assert pc1.call("GET", "/api/health")["games"] == 1
assert fails(lambda: pc1.call("POST", "/api/register", {"email": "nope", "password": "longenough", "name": "Ann"}), 400)
assert fails(lambda: pc1.call("POST", "/api/register", {"email": "ann@example.com", "password": "short", "name": "Ann"}), 400)
pc1.keep(pc1.call("POST", "/api/register", {"email": "Ann@Example.com", "password": "test-pass-1", "name": "Ann"}))
assert pc1.signed_in and pc1.s["email"] == "ann@example.com"
assert fails(lambda: pc2.call("POST", "/api/register", {"email": "ann@example.com", "password": "test-pass-1", "name": "Ann2"}), 409)
assert fails(lambda: pc2.call("POST", "/api/login", {"email": "ann@example.com", "password": "wrong-pass"}), 401)
assert fails(lambda: pc2.call("POST", "/api/sync", {"state": {}}), 401)
# computer 1 has the 23 trophies of the story above; computer 2 has two others plus more wins
d1 = {"games": {P.id: {"ach": {i: 1000.0 + n for n, i in enumerate(sorted(AC2.unlocked))}, "ach_memo": {"wins": 12, "maps": [1, 4]},
                         "playtime": 500, "rom": "C:/secret/path.nes", "ui": {"pos": [1, 2]}}},
      "profile": {"owned": ["graphite"], "use": {"theme": "graphite"}}, "settings": {"moby_key": "never-sent"}}
snap = snapshot(d1); assert "rom" not in snap["games"][P.id] and "ui" not in snap["games"][P.id] and "settings" not in snap
r1 = pc1.call("POST", "/api/sync", {"state": snap})
assert r1["summary"]["points"] == 505 and r1["summary"]["level"] == 3 and r1["rank"] == 1
pc2.keep(pc2.call("POST", "/api/login", {"email": "ann@example.com", "password": "test-pass-1"}))
d2 = {"games": {P.id: {"ach": {"metal10": 2000.0, "out": 900.0, "not-a-real-id": 5.0}, "ach_memo": {"wins": 40, "maps": [4, 9]}, "playtime": 90}},
      "profile": {}}
r2 = pc2.call("POST", "/api/sync", {"state": snapshot(d2)})
g2 = r2["state"]["games"][P.id]
assert r2["summary"]["points"] == 535 and "not-a-real-id" not in g2["ach"] and g2["ach"]["out"] == 900.0      # earliest time kept
assert g2["ach_memo"] == {"wins": 40, "maps": [1, 4, 9]} and g2["playtime"] == 500 and r2["state"]["profile"]["use"] == {"theme": "graphite"}
merge_into(d2["games"][P.id], g2); merge_into(d2["profile"], r2["state"]["profile"])
assert len(d2["games"][P.id]["ach"]) == 25 and d2["profile"]["owned"] == ["graphite"]   # 23 + its own 2: it has it all
# a cheater cannot send points, only ids the catalogue knows; a second player ranks below
pc3 = Account({}); pc3.keep(pc3.call("POST", "/api/register", {"email": "bob@example.com", "password": "test-pass-2", "name": "Bob"}))
r3 = pc3.call("POST", "/api/sync", {"state": {"games": {P.id: {"ach": {"out": 1.0}}, "fake_game": {"ach": {"x": 1}}}, "points": 99999}})
assert r3["summary"]["points"] == 5 and r3["rank"] == 2 and "fake_game" not in r3["state"]["games"]
board = pc3.call("GET", "/api/leaderboard?limit=10")
assert [(p["rank"], p["name"], p["points"]) for p in board["players"]] == [(1, "Ann", 535), (2, "Bob", 5)] and board["total"] == 2
assert "email" not in json.dumps(board) and "example.com" not in json.dumps(board)
# supporters are marked on the server by hand; the client cannot claim it
pc3.call("POST", "/api/sync", {"state": {"supporter": "hero", "profile": {"supporter": "hero"}}})
assert pc3.call("GET", "/api/supporters") == {"supporters": []}
assert svc.set_supporter("Ann@example.com", "knight") and not svc.set_supporter("nobody@example.com", "hero")
assert pc3.call("GET", "/api/supporters") == {"supporters": [{"name": "Ann", "tier": "knight"}]}
assert [p.get("supporter") for p in pc3.call("GET", "/api/leaderboard")["players"]] == ["knight", ""]
assert svc.set_supporter("ann@example.com", "none") and pc3.call("GET", "/api/supporters") == {"supporters": []}
# visits and downloads: one visitor a day, sources by host, no bots, no unknown pages, no stored address
UA = "Mozilla/5.0 (test)"
svc.hit("1.1.1.1", UA, "/", "https://www.reddit.com/r/dragonquest/x"); svc.hit("1.1.1.1", UA, "/support.html", "https://retro.dieergames.hu/")
svc.hit("2.2.2.2", UA, "/", ""); svc.hit("2.2.2.2", UA, "/", "Reddit-DQ"); svc.hit("3.3.3.3", "Googlebot/2.1", "/", "")
svc.hit("3.3.3.3", UA, "/wp-admin", ""); svc.hit("3.3.3.3", UA, None, "<script>")
svc.download("1.1.1.1", UA); svc.download("1.1.1.1", UA); svc.download("9.9.9.9", "curl/8.0")
assert pc3.call("POST", "/api/hit", {"page": "/", "ref": "x.com"}) == {}          # the test client is a program: not counted
import hashlib as _h
os.environ["RC_ADMIN"] = "00" * 16 + ":" + _h.scrypt(b"admin-test-pass", salt=bytes(16), n=2 ** 14, r=8, p=1, dklen=32).hex()
stats = svc.admin_stats("9.9.9.9", "admin-test-pass"); today = stats["days"][0]
assert (today["views"], today["visitors"], today["downloads"]) == (4, 2, 1) and len(stats["days"]) == 30
assert stats["total"] == {"views": 4, "visitors": 2, "downloads": 1}
assert {s["ref"]: s["views"] for s in stats["sources"]} == {"reddit.com": 1, "direct": 1, "reddit-dq": 1}
assert {p["page"]: p["views"] for p in stats["pages"]} == {"/": 3, "/support": 1} and stats["accounts"]["all"] == 2
svc.hit("1.1.1.1", UA, "/guides/dragon-warrior-walkthrough", ""); svc.hit("1.1.1.1", UA, "/guides/../etc", "")
assert {p["page"] for p in svc.admin_stats("9.9.9.9", "admin-test-pass")["pages"]} == {"/", "/support", "/guides/dragon-warrior-walkthrough"}
for bad in ("wrong-pass", ""):
    try:
        svc.admin_stats("9.9.9.9", bad); raise SystemExit("admin stats opened with a wrong password")
    except SRV.Fail as f:
        assert f.status == 401
dump = json.dumps(svc.db.execute("SELECT * FROM seen").fetchall() + svc.db.execute("SELECT * FROM views").fetchall())
assert "1.1.1.1" not in dump and "2.2.2.2" not in dump
import http.client as _hc
c = _hc.HTTPConnection("127.0.0.1", httpd.server_address[1]); c.request("GET", "/api/download", headers={"User-Agent": UA})
r = c.getresponse(); r.read(); assert r.status == 302 and r.getheader("Location") == SRV.DOWNLOAD and "github.com" in SRV.DOWNLOAD
c.request("GET", "/api/admin/stats", headers={"Authorization": "Bearer admin-test-pass"}); r = c.getresponse()
assert r.status == 200 and json.loads(r.read())["total"]["downloads"] == 2; c.close()
del os.environ["RC_ADMIN"]
# ideas: a new one waits for the owner, then everyone sees it; one vote per account, taken back by a second call
anon = Account({})
assert anon.call("GET", "/api/ideas") == {"ideas": [], "signed_in": False}
assert fails(lambda: anon.call("POST", "/api/ideas", {"title": "A second game", "text": "x"}), 401)
assert fails(lambda: pc3.call("POST", "/api/ideas", {"title": "short", "text": ""}), 400)
i1 = pc3.call("POST", "/api/ideas", {"title": "  A second   game ", "text": "Final Fantasy\n  would be  nice"})["id"]
mine = pc3.call("GET", "/api/ideas")
assert mine["signed_in"] and [(i["title"], i["text"], i["status"], i["votes"], i["voted"], i["mine"], i["name"]) for i in mine["ideas"]] == [
    ("A second game", "Final Fantasy\nwould be nice", "new", 1, True, True, "Bob")]
assert anon.call("GET", "/api/ideas")["ideas"] == [] and pc1.call("GET", "/api/ideas")["ideas"] == []      # not public yet
assert fails(lambda: pc1.call("POST", "/api/ideas/vote", {"id": i1}), 400)                                  # nor votable
os.environ["RC_ADMIN"] = "00" * 16 + ":" + _h.scrypt(b"admin-test-pass", salt=bytes(16), n=2 ** 14, r=8, p=1, dklen=32).hex()
try:
    svc.admin_idea("9.9.9.9", "wrong", i1, "open"); raise SystemExit("an idea was changed with a wrong password")
except SRV.Fail as f:
    assert f.status == 401
assert svc.admin_ideas("9.9.9.9", "admin-test-pass")["ideas"][0]["status"] == "new"
svc.admin_idea("9.9.9.9", "admin-test-pass", i1, "open", "Good one")
i2 = svc.admin_idea("9.9.9.9", "admin-test-pass", None, "planned", None, "Rarity of achievements", "How many players have each one")["id"]
i3 = pc1.call("POST", "/api/ideas", {"title": "Something rude", "text": ""})["id"]
svc.admin_idea("9.9.9.9", "admin-test-pass", i3, "declined")
assert pc1.call("POST", "/api/ideas/vote", {"id": i1}) == {"ok": True, "voted": True, "votes": 2}
assert pc1.call("POST", "/api/ideas/vote", {"id": i2})["votes"] == 1 and fails(lambda: anon.call("POST", "/api/ideas/vote", {"id": i1}), 401)
assert fails(lambda: pc1.call("POST", "/api/ideas/vote", {"id": 999}), 400) and fails(lambda: pc1.call("POST", "/api/ideas/vote", {"id": "1"}), 400)
pub = anon.call("GET", "/api/ideas")["ideas"]
assert [(i["title"], i["status"], i["votes"], i["name"], i["reply"], i["voted"]) for i in pub] == [
    ("Rarity of achievements", "planned", 1, "Retro Companion", "", False), ("A second game", "open", 2, "Bob", "Good one", False)]
assert "example.com" not in json.dumps(pub)
assert [i["title"] for i in pc1.call("GET", "/api/ideas")["ideas"]] == ["Rarity of achievements", "A second game", "Something rude"]
assert pc1.call("POST", "/api/ideas/vote", {"id": i1}) == {"ok": True, "voted": False, "votes": 1}
c = _hc.HTTPConnection("127.0.0.1", httpd.server_address[1])
c.request("POST", "/api/admin/idea", json.dumps({"id": i2, "status": "done"}), {"Authorization": "Bearer admin-test-pass", "Content-Type": "application/json"})
r = c.getresponse(); assert r.status == 200 and json.loads(r.read())["ok"]; c.close()
assert svc.admin_stats("9.9.9.9", "admin-test-pass")["ideas_waiting"] == 0
del os.environ["RC_ADMIN"]
# password reset by mailed code, then the old token and the old password are dead
pc1.call("POST", "/api/reset/request", {"email": "ann@example.com"}); pc1.call("POST", "/api/reset/request", {"email": "nobody@example.com"})
assert len(mails) == 1 and mails[0][0] == "ann@example.com"
code = re.search(r"\b(\d{6})\b", mails[0][1]).group(1) if (re := __import__("re")) else None
assert fails(lambda: pc1.call("POST", "/api/reset/confirm", {"email": "ann@example.com", "code": "000000" if code != "000000" else "111111", "password": "test-pass-3"}), 400)
pc1.keep(pc1.call("POST", "/api/reset/confirm", {"email": "ann@example.com", "code": code, "password": "test-pass-3"}))
assert fails(lambda: pc2.call("POST", "/api/sync", {"state": {}}), 401) and fails(lambda: pc2.call("POST", "/api/login", {"email": "ann@example.com", "password": "test-pass-1"}), 401)
# deleting needs the password and removes the player from the board
assert fails(lambda: pc3.call("POST", "/api/account/delete", {"password": "wrong-pass"}), 401)
pc3.call("POST", "/api/account/delete", {"password": "test-pass-2"})
assert pc3.call("GET", "/api/leaderboard")["total"] == 1 and fails(lambda: pc3.call("POST", "/api/sync", {"state": {}}), 401)
left = anon.call("GET", "/api/ideas")["ideas"]            # Bob is gone: his public idea stays without his name, his vote goes
assert [(i["title"], i["name"], i["votes"]) for i in left] == [("A second game", "A former player", 0), ("Rarity of achievements", "Retro Companion", 1)]
row = svc.db.execute("SELECT pw, state FROM users").fetchone(); assert b"test-pass" not in row[0] and "test-pass" not in row[1]
httpd.shutdown(); del os.environ["RC_SERVER"]; print("account server OK")
# a beaten enemy: the HP byte wraps below zero and must read as 0, never as a full bar; the log lines
from companion.overlay import Ctx
def G(**k):
    r = bytearray(0x8000); d = dict(map=1, level=5, hp=20, maxhp=30); d.update(k); setram(r, **d)
    return DW.Game(bytes(r[:0x110]), bytes(r[0x6000:0x6030]))
g = G(en_id=0, en_hp=245, en_stats=EN[0], chr=3); assert g.en_hp == 0 and g.in_battle
P._fight = (0, 3); b = P.view(g, Ctx(P.steps[0], 0, False))["battle"]
assert b["title"] == "SLIME   defeated" and b["frac"] == 0 and "more hit" not in " ".join(b["lines"])
g = G(en_id=0, en_hp=3, en_stats=EN[0], chr=3); assert g.en_hp == 3
assert "HP 3 / 3" in P.view(g, Ctx(P.steps[0], 0, False))["battle"]["title"]
assert G(en_id=35, en_hp=160, en_stats=EN[35], chr=3).en_hp == 160           # the Stoneman's full 160 is real
before = G(exp=10, gold=5, en_id=0, en_stats=EN[0], en_hp=2, chr=3)
assert P.events(G(exp=11, gold=7, en_id=0, en_stats=EN[0], en_hp=250, chr=3), before) == ["Defeated Slime \u00b7 +1 XP, +2 G"]
assert P.events(G(level=7), G(level=6)) == ["Reached level 7. Learned SLEEP"]
assert P.events(G(map=7), G()) == ["Entered Kol"] and P.events(G(), None) == []
assert P.events(G(items=[5]), G()) == ["Got Fairy Flute"] and P.events(G(equip=0x60), G(equip=0x20)) == ["Equipped Copper Sword"]
assert P.events(G(hp=0), G()) == ["Fell in battle. Half of the gold is lost"]
print("battle bar and log lines OK")
# the full-size map: every place has a status that follows the walkthrough
def AT(cur, seen=(5, 4, 1, 8), g=None):
    return P.atlas(g, Ctx(P.steps[cur], cur, False, cur, frozenset(s["id"] for s in P.steps[:cur]), frozenset(seen)))
at = AT(8, (5, 4, 1, 8, 9, 7))                          # on "Fairy Flute in Kol"
st = {m["name"]: m["status"] for m in at["maps"][1]["marks"]}
assert st["Kol"] == "now" and st["Brecconary"] == "done" and st["Rimuldar"] == "later", st
assert st["Mountain Cave"] == "optional" and st["Erdrick's Cave"] == "optional"     # never needed / skipped unseen
assert st["Garinham"] == "later" and st["Erdrick's Token (swamp)"] == "later"       # the harp waits under Garinham
assert st["Swamp Cave (north entrance)"] == st["Swamp Cave (south entrance)"] == "later"
assert len(at["order"]) == 29 and at["order"][0] == 1 and at["here"] is None
kol = {m["name"]: m for m in at["maps"][0x07]["marks"]}
assert kol["Fairy Flute in Kol"]["status"] == "now" and (kol["Fairy Flute in Kol"]["x"], kol["Fairy Flute in Kol"]["y"]) == (9, 6)
assert kol["To Alefgard (overworld)"]["goto"] == 1
gg = {m["name"]: m for m in at["maps"][0x1A]["marks"]}
assert any(n.endswith("Silver Harp") for n in gg) and gg["Silver Harp (Garin's Grave)"]["status"] == "later"
assert len(at["maps"][1]["areas"]) == 64 and "Slime" in at["maps"][1]["areas"][3 * 8 + 2][4][0]
end = AT(len(P.steps) - 1, range(1, 0x1E))
assert all(m["status"] in ("done", "now", "optional") for m in end["maps"][1]["marks"])
g = G(map=1, x=45, y=43)
live = AT(1, (5, 4, 1), g)
assert live["here"] == 1 and live["player"] == (45, 43) and live["maps"][1]["path"][-1] == (48, 41)
assert {m["name"]: m["status"] for m in live["maps"][1]["marks"]}["Brecconary"] == "now"
print("full-size map OK")

# the chime is made in code; the portraits and the news list are complete
import wave
from companion import avatars, sound
from companion.news import NEWS
w = wave.open(sound.path("trophy"), "rb")
assert w.getframerate() == sound.RATE and 0.8 < w.getnframes() / float(sound.RATE) < 1.6
w.close()
assert len(avatars.BUILT_IN) == 20 and len({s[0] for s in avatars.BUILT_IN}) == 20
assert all(len(avatars.portrait(s)) == 16 and all(len(r) == 16 for r in avatars.portrait(s)) for s in avatars.BUILT_IN)
assert len({str(avatars.portrait(s)) for s in avatars.BUILT_IN}) == 20
assert avatars.keep("x.jpg") == "Choose a PNG or GIF picture" and not avatars.setting_ok({"id": 20})
assert NEWS[0]["title"] == "Version " + __import__("companion").VERSION
assert [n["date"] for n in NEWS] == sorted((n["date"] for n in NEWS), reverse=True)
# the shop's choices: one chime, one pop-up style, one frame in use at a time
from companion import discord
from companion.profile import ONE_OF, KINDS
ids = [i["id"] for i in SHOP]
assert len(ids) == len(set(ids)) and {i["kind"] for i in SHOP} == {k for k, _ in KINDS}
assert all(any(i["id"] == d and i["kind"] == k and i["price"] == 0 for i in SHOP) for k, d in ONE_OF.items())
assert all(i["id"] in sound.SOUNDS for i in SHOP if i["kind"] == "chime")
assert all(i["id"] in ("plain",) or i["id"] in __import__("companion.theme", fromlist=["x"]).TROPHY
           for i in SHOP if i["kind"] == "frame")
class _A:
    items = [{"id": "a", "points": 600}]; unlocked = {"a": 1}
    def count(self): return 1
    def points(self): return 600
pd = {}
pq = Profile(pd, {"g": _A()}, lambda: None)
assert pq.choice("chime") == "trophy" and pq.choice("frame") == "plain" and pq.level() == 4      # 600 + platinum 100
coin = next(i for i in SHOP if i["id"] == "coin"); banner = next(i for i in SHOP if i["id"] == "banner")
assert pq.buy(coin) and pq.choice("chime") == "coin" and pq.buy(banner) and pq.choice("popup") == "banner"
pq.use(next(i for i in SHOP if i["id"] == "trophy")); assert pq.choice("chime") == "trophy" and pq.owns("coin")
assert pq.spent() == 250 and not pq.buy(next(i for i in SHOP if i["id"] == "platinum"))        # needs level 7
pd["use"]["frame"] = "gold"; assert pq.choice("frame") == "plain"                                 # not owned: the default
for nm in sound.SOUNDS:
    w = wave.open(sound.path(nm), "rb"); assert 0.5 < w.getnframes() / float(sound.RATE) < 1.8; w.close()
# Discord's wire format, and a command without a reply reaching RetroArch
f = discord.frame(1, discord.command(discord.activity("Dragon Warrior", "Lv 9 · Kol · step 9 of 32", 100), pid=7))
op, n = __import__("struct").unpack("<II", f[:8]); body = json.loads(f[8:].decode("utf-8"))
assert (op, n) == (1, len(f) - 8) and body["cmd"] == "SET_ACTIVITY" and body["args"]["pid"] == 7
assert body["args"]["activity"] == {"details": "Dragon Warrior", "state": "Lv 9 · Kol · step 9 of 32", "timestamps": {"start": 100}}
assert not discord.Presence("").usable and discord.Presence("").set("x") is None
print("shop choices, Discord frame OK")
print("sound, portraits, news OK")
# updating: a newer release is found, downloaded, checked against its checksum and swapped in
from companion import update as UP
assert UP.parse("v0.10") == (0, 10) and UP.newer("v0.10", "0.9") and not UP.newer("v0.8", "0.8") and not UP.newer("nightly", "0.1")
assert UP.newer("1.0", "0.99") and not UP.newer("v0.7", "0.8") and UP.parse("") == ()
NEWEXE = b"MZ" + bytes(range(256)) * 40
REL = {"tag": "v9.1", "sum": __import__("hashlib").sha256(NEWEXE).hexdigest(), "assets": True}
class _Rel(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        base = "http://127.0.0.1:%d/files/" % self.server.server_address[1]
        if self.path == "/latest":
            body = json.dumps({"tag_name": REL["tag"], "body": "Notes of the release", "html_url": "https://example.org/rel",
                               "assets": [{"name": "RetroCompanion.exe", "browser_download_url": base + "RetroCompanion.exe"},
                                          {"name": "SHA256.txt", "browser_download_url": base + "SHA256.txt"}] if REL["assets"] else []}).encode()
        elif self.path == "/files/RetroCompanion.exe":
            body = NEWEXE
        elif self.path == "/files/SHA256.txt":
            body = ("%s  RetroCompanion.exe\n" % REL["sum"]).encode()
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
rel = http.server.HTTPServer(("127.0.0.1", 0), _Rel)
threading.Thread(target=rel.serve_forever, daemon=True).start()
RB = "http://127.0.0.1:%d" % rel.server_address[1]
info = UP.check("0.8", RB + "/latest", RB + "/files/")
assert info["version"] == "9.1" and info["notes"] == "Notes of the release" and info["url"].endswith("RetroCompanion.exe")
assert UP.check("9.1", RB + "/latest", RB + "/files/") is None and UP.check("10.0", RB + "/latest", RB + "/files/") is None
assert UP.check("0.8", RB + "/latest")["url"] == ""                 # files from anywhere but the project's releases are not taken
try:
    UP.check("0.8", RB + "/nothing"); raise SystemExit("a missing release did not fail")
except UP.UpdateError:
    pass
folder = tempfile.mkdtemp(); exe = os.path.join(folder, "RetroCompanion.exe")
with open(exe, "wb") as fh: fh.write(b"the old program")
new, old = UP.paths(exe)
assert os.path.basename(new) == "RetroCompanion.new.exe" and os.path.basename(old) == "RetroCompanion.old.exe"
seen_progress = []
assert UP.download(info, new, lambda d, t: seen_progress.append((d, t))) == new and seen_progress[-1] == (len(NEWEXE), len(NEWEXE))
assert UP.swap(exe, new) == exe and open(exe, "rb").read() == NEWEXE and open(old, "rb").read() == b"the old program"
UP.cleanup(exe); assert os.listdir(folder) == ["RetroCompanion.exe"] and UP.can_install(exe) == ""
REL["sum"] = "0" * 64                                               # a file that does not match its checksum is thrown away
try:
    UP.download(UP.check("0.8", RB + "/latest", RB + "/files/"), new); raise SystemExit("a wrong checksum was accepted")
except UP.UpdateError:
    assert not os.path.exists(new) and open(exe, "rb").read() == NEWEXE
REL["assets"] = False
try:
    UP.download(UP.check("0.8", RB + "/latest", RB + "/files/"), new); raise SystemExit("a release without files was accepted")
except UP.UpdateError:
    pass
assert "source" in UP.can_install()                                 # the tests run from source: nothing to replace
rel.shutdown(); print("update OK")
print("ALL OK")
