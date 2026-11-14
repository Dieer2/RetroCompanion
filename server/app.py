"""Retro Companion server: accounts, the synced player data and the leaderboard.

Standard library only: http.server + sqlite3. It listens on 127.0.0.1 and is meant to sit
behind a reverse proxy that does HTTPS (see deploy/). Everything is JSON under /api/.

    POST   /api/register        {email, password, name}      -> {token, user}
    POST   /api/login           {email, password}            -> {token, user}
    POST   /api/logout                                        (token)
    POST   /api/sync            {state}                       (token) -> {state, user}
    GET    /api/leaderboard     ?limit=50                     -> {players, total}
    GET    /api/supporters                                    -> {supporters: [{name, tier}]}
    POST   /api/password        {old, new}                    (token)
    POST   /api/reset/request   {email}                       mails a code, if mail is set up
    POST   /api/reset/confirm   {email, code, password}       -> {token, user}
    POST   /api/account/delete  {password}                    (token) removes the account and its data
    GET    /api/health
    POST   /api/hit             {page, ref}                   counts a page view (no address is stored)
    GET    /api/download                                      counts a download, redirects to the file
    GET    /api/admin/stats                                   (admin password as the token) -> visits, sources, downloads

The token goes in "Authorization: Bearer <token>". Passwords are stored as scrypt hashes,
tokens and reset codes as SHA-256 hashes. Points are never taken from the client: the server
recomputes them from the unlocked achievement ids and its own catalogue (catalogue.json,
made from the game plugins by make_catalogue.py). What a client claims to have unlocked
cannot be checked, so the leaderboard is an honour board.

Supporters are marked by hand, never by the client (run as the user that owns the database):

    python app.py supporter <email> <squire|knight|hero|none>
    python app.py supporter                                   lists them

Visit counting keeps no addresses: per day it stores view counts by page and source, and
a one-way fingerprint of address + browser made with a key that is replaced every day, only
to tell a returning visitor from a new one on that day. The admin password is set on the
server with rc-set-admin-key (RC_ADMIN = salt:scrypt hash, both hex).

Environment: RC_DB (database file), RC_PORT (default 8377), RC_CATALOGUE, and for password
reset mails RESEND_API_KEY and RC_MAIL_FROM.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # deployed layout: companion/ sits next to this file
sys.path.insert(0, os.path.dirname(HERE))      # in the project: one level up

from companion import VERSION                                              # noqa: E402
from companion.merge import merge_into                                     # noqa: E402
from companion.profile import GRADES, PLATINUM_POINTS, TITLES, grade, level_floor   # noqa: E402

MAX_BODY = 256 * 1024
TOKEN_DAYS = 180
RESET_MINUTES = 30
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,24}$")
LIMITS = {"auth": (10, 600), "register": (5, 3600), "reset": (5, 3600), "sync": (120, 600), "read": (120, 60),
          "hit": (60, 60), "admin": (20, 600)}
PAGES = {"/": "/", "/index.html": "/", "/support": "/support", "/support.html": "/support",
         "/privacy": "/privacy", "/privacy.html": "/privacy"}
GUIDE_RE = re.compile(r"^/guides(/[a-z0-9-]{1,80})?$")
DOWNLOAD = "/download/RetroCompanion.exe"
BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|monitor|curl|wget|python|headless|scan|fetch|lighthouse|^retrocompanion|^$", re.I)
OWN_HOSTS = ("dieergames.hu",)


class Fail(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status, self.message = status, message


def pw_hash(password, salt):
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


TIERS = ("squire", "knight", "hero")      # supporter tiers, lowest first


class Service:
    def __init__(self, db_path, catalogue, mail=None):
        self.cat = catalogue                   # {"games": {gid: {"title", "ach": {id: points}}}}
        self.mail = mail                       # callable(to, subject, text) or None
        self.lock = threading.RLock()          # one connection for all threads: every use goes through it
        self.hits = {}
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                pw BLOB NOT NULL, salt BLOB NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                state TEXT NOT NULL DEFAULT '{}', points INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS tokens (hash TEXT PRIMARY KEY, user INTEGER NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS resets (hash TEXT PRIMARY KEY, user INTEGER NOT NULL, created REAL NOT NULL, tries INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS users_points ON users (points DESC, updated ASC);
            CREATE TABLE IF NOT EXISTS views (day TEXT NOT NULL, page TEXT NOT NULL, ref TEXT NOT NULL, n INTEGER NOT NULL,
                PRIMARY KEY (day, page, ref));
            CREATE TABLE IF NOT EXISTS daily (day TEXT PRIMARY KEY, visitors INTEGER NOT NULL DEFAULT 0,
                downloads INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS seen (day TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY (day, hash));
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if "supporter" not in [r[1] for r in self.db.execute("PRAGMA table_info(users)")]:
            self.db.execute("ALTER TABLE users ADD COLUMN supporter TEXT NOT NULL DEFAULT ''")
        self.db.commit()

    # -- helpers ---------------------------------------------------------------
    def one(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def rows(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def limit(self, kind, who):
        """Sliding window per kind and address; raises 429 when it is used up."""
        n, window = LIMITS[kind]
        now = time.time()
        with self.lock:
            q = [t for t in self.hits.get((kind, who), ()) if now - t < window]
            if len(q) >= n:
                self.hits[(kind, who)] = q
                raise Fail(429, "Too many attempts. Try again later")
            q.append(now)
            self.hits[(kind, who)] = q
            if len(self.hits) > 20000:
                self.hits.clear()

    def summary(self, state):
        """Points, level and trophies of a state, from the server's own catalogue."""
        trophies = dict.fromkeys(GRADES, 0)
        points = games = 0
        for gid, info in self.cat["games"].items():
            got = [i for i in (state.get("games", {}).get(gid, {}).get("ach") or {}) if i in info["ach"]]
            if not got:
                continue
            games += 1
            for i in got:
                points += info["ach"][i]
                trophies[grade(info["ach"][i])] += 1
            if len(got) == len(info["ach"]):
                points += PLATINUM_POINTS
                trophies["platinum"] += 1
        level = 1
        while level_floor(level + 1) <= points:
            level += 1
        return {"points": points, "level": level, "title": [t for need, t in TITLES if need <= level][-1],
                "trophies": trophies, "games": games}

    def clean(self, state):
        """Keep only what belongs in a synced state: known games, plain JSON, sane size."""
        if not isinstance(state, dict):
            raise Fail(400, "Bad state")
        games = {}
        for gid, g in (state.get("games") or {}).items():
            if gid in self.cat["games"] and isinstance(g, dict):
                g = dict(g)
                ach = g.get("ach")
                if isinstance(ach, dict):
                    now = time.time()
                    g["ach"] = {i: min(float(t), now) for i, t in ach.items()
                                if i in self.cat["games"][gid]["ach"] and isinstance(t, (int, float)) and t > 0}
                else:
                    g.pop("ach", None)
                games[gid] = g
        prof = state.get("profile") if isinstance(state.get("profile"), dict) else {}
        return {"games": games, "profile": {k: prof[k] for k in ("owned", "use") if k in prof}}

    def user_out(self, row):
        return {"email": row[1], "name": row[2], "created": row[3]}

    def new_token(self, uid):
        token = secrets.token_urlsafe(32)
        self.db.execute("INSERT INTO tokens VALUES (?, ?, ?)", (digest(token), uid, time.time()))
        return token

    def auth(self, token):
        if not token:
            raise Fail(401, "Sign in first")
        row = self.one("SELECT user, created FROM tokens WHERE hash = ?", (digest(token),))
        if not row or time.time() - row[1] > TOKEN_DAYS * 86400:
            raise Fail(401, "Your sign-in has expired. Sign in again")
        return row[0]

    @staticmethod
    def check_password(password):
        if not isinstance(password, str) or not 8 <= len(password) <= 200:
            raise Fail(400, "The password needs at least 8 characters")

    # -- accounts --------------------------------------------------------------
    def register(self, who, email, password, name):
        self.limit("register", who)
        email = (email or "").strip().lower() if isinstance(email, str) else ""
        name = " ".join((name or "").split()) if isinstance(name, str) else ""
        if not EMAIL_RE.match(email):
            raise Fail(400, "That does not look like an email address")
        if not 2 <= len(name) <= 24:
            raise Fail(400, "The player name needs 2 to 24 characters")
        self.check_password(password)
        salt = secrets.token_bytes(16)
        hashed = pw_hash(password, salt)            # slow on purpose: outside the lock
        now = time.time()
        with self.lock:
            try:
                cur = self.db.execute("INSERT INTO users (email, name, pw, salt, created, updated) VALUES (?,?,?,?,?,?)",
                                      (email, name, hashed, salt, now, now))
            except sqlite3.IntegrityError:
                raise Fail(409, "There is already an account with this email address")
            token = self.new_token(cur.lastrowid)
            self.db.commit()
        return {"token": token, "user": {"email": email, "name": name, "created": now}}

    def login(self, who, email, password):
        self.limit("auth", who)
        email = (email or "").strip().lower() if isinstance(email, str) else ""
        row = self.one("SELECT id, email, name, created, pw, salt FROM users WHERE email = ?", (email,))
        probe = pw_hash(password if isinstance(password, str) else "", row[5] if row else b"0" * 16)
        if not row or not hmac.compare_digest(probe, row[4]):
            raise Fail(401, "Wrong email address or password")
        with self.lock:
            token = self.new_token(row[0])
            self.db.commit()
        return {"token": token, "user": self.user_out(row)}

    def logout(self, token):
        with self.lock:
            self.db.execute("DELETE FROM tokens WHERE hash = ?", (digest(token or ""),))
            self.db.commit()
        return {"ok": True}

    def change_password(self, who, token, old, new):
        self.limit("auth", who)
        uid = self.auth(token)
        self.check_password(new)
        row = self.one("SELECT pw, salt FROM users WHERE id = ?", (uid,))
        if not hmac.compare_digest(pw_hash(old if isinstance(old, str) else "", row[1]), row[0]):
            raise Fail(401, "The current password is wrong")
        salt = secrets.token_bytes(16)
        hashed = pw_hash(new, salt)
        with self.lock:
            self.db.execute("UPDATE users SET pw = ?, salt = ? WHERE id = ?", (hashed, salt, uid))
            self.db.execute("DELETE FROM tokens WHERE user = ? AND hash != ?", (uid, digest(token)))
            self.db.commit()
        return {"ok": True}

    def reset_request(self, who, email):
        self.limit("reset", who)
        if self.mail is None:
            raise Fail(503, "Password reset by email is not set up on this server yet")
        email = (email or "").strip().lower() if isinstance(email, str) else ""
        row = self.one("SELECT id FROM users WHERE email = ?", (email,))
        if row:                                    # the answer is the same either way: no account probing
            code = "%06d" % secrets.randbelow(10 ** 6)
            with self.lock:
                self.db.execute("DELETE FROM resets WHERE user = ?", (row[0],))
                self.db.execute("INSERT INTO resets VALUES (?, ?, ?, 0)", (digest("%d:%s" % (row[0], code)), row[0], time.time()))
                self.db.commit()
            self.mail(email, "Your Retro Companion password reset code",
                      "Your code is %s\n\nEnter it in Retro Companion to choose a new password. It works for %d minutes.\n"
                      "If you did not ask for this, ignore this message: nothing has changed." % (code, RESET_MINUTES))
        return {"ok": True}

    def reset_confirm(self, who, email, code, password):
        self.limit("auth", who)
        self.check_password(password)
        email = (email or "").strip().lower() if isinstance(email, str) else ""
        row = self.one("SELECT id, email, name, created FROM users WHERE email = ?", (email,))
        bad = Fail(400, "The code is wrong or has expired")
        if not row:
            raise bad
        with self.lock:
            r = self.db.execute("SELECT hash, created, tries FROM resets WHERE user = ?", (row[0],)).fetchone()
            if not r or time.time() - r[1] > RESET_MINUTES * 60 or r[2] >= 5:
                raise bad
            if not hmac.compare_digest(r[0], digest("%d:%s" % (row[0], str(code).strip()))):
                self.db.execute("UPDATE resets SET tries = tries + 1 WHERE user = ?", (row[0],))
                self.db.commit()
                raise bad
            salt = secrets.token_bytes(16)
            self.db.execute("UPDATE users SET pw = ?, salt = ? WHERE id = ?", (pw_hash(password, salt), salt, row[0]))
            self.db.execute("DELETE FROM resets WHERE user = ?", (row[0],))
            self.db.execute("DELETE FROM tokens WHERE user = ?", (row[0],))
            token = self.new_token(row[0])
            self.db.commit()
        return {"token": token, "user": self.user_out(row)}

    def delete_account(self, who, token, password):
        self.limit("auth", who)
        uid = self.auth(token)
        row = self.one("SELECT pw, salt FROM users WHERE id = ?", (uid,))
        if not hmac.compare_digest(pw_hash(password if isinstance(password, str) else "", row[1]), row[0]):
            raise Fail(401, "The password is wrong")
        with self.lock:
            for table, col in (("tokens", "user"), ("resets", "user"), ("users", "id")):
                self.db.execute("DELETE FROM %s WHERE %s = ?" % (table, col), (uid,))
            self.db.commit()
        return {"ok": True}

    # -- data ------------------------------------------------------------------
    def sync(self, who, token, state):
        self.limit("sync", who)
        uid = self.auth(token)
        incoming = self.clean(state)
        with self.lock:
            row = self.db.execute("SELECT id, email, name, created, state FROM users WHERE id = ?", (uid,)).fetchone()
            merged = merge_into(json.loads(row[4] or "{}"), incoming)
            text = json.dumps(merged, separators=(",", ":"))
            if len(text) > MAX_BODY:
                raise Fail(413, "Too much data")
            s = self.summary(merged)
            self.db.execute("UPDATE users SET state = ?, points = ?, summary = ?, updated = ? WHERE id = ?",
                            (text, s["points"], json.dumps(s), time.time(), uid))
            self.db.commit()
            rank = self.db.execute("SELECT COUNT(*) FROM users WHERE points > ?", (s["points"],)).fetchone()[0] + 1
        return {"state": merged, "user": self.user_out(row), "summary": s, "rank": rank}

    def leaderboard(self, who, limit=50):
        self.limit("read", who)
        limit = max(1, min(100, int(limit)))
        rows = self.rows("SELECT name, points, summary, supporter FROM users WHERE points > 0 "
                         "ORDER BY points DESC, updated ASC LIMIT ?", (limit,))
        players = []
        for i, (name, points, summary, supporter) in enumerate(rows, 1):
            s = json.loads(summary or "{}")
            players.append({"rank": i, "name": name, "points": points, "level": s.get("level", 1),
                            "title": s.get("title", ""), "trophies": s.get("trophies", {}), "games": s.get("games", 0),
                            "supporter": supporter})
        total = self.one("SELECT COUNT(*) FROM users WHERE points > 0")[0]
        return {"players": players, "total": total}

    # -- supporters: set by hand from the command line, shown on the website ----------
    def supporters(self, who):
        self.limit("read", who)
        rows = self.rows("SELECT name, supporter FROM users WHERE supporter != '' ORDER BY created ASC")
        rows.sort(key=lambda r: -TIERS.index(r[1]) if r[1] in TIERS else 0)
        return {"supporters": [{"name": n, "tier": t} for n, t in rows]}

    # -- visits and downloads: counts only, no addresses -----------------------------
    def _fresh(self, who, ua, kind):
        """(day, True the first time this visitor does `kind` today). The fingerprint key lives one day."""
        day = time.strftime("%Y-%m-%d", time.gmtime())
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key = 'salt'").fetchone()
            if not row or not row[0].startswith(day + ":"):
                row = (day + ":" + secrets.token_hex(16),)
                self.db.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('salt', ?)", row)
                self.db.execute("DELETE FROM seen WHERE day < ?", (day,))
            h = hashlib.sha256(("%s|%s|%s|%s" % (row[0], kind, who, ua)).encode("utf-8", "replace")).hexdigest()[:24]
            new = self.db.execute("INSERT OR IGNORE INTO seen (day, hash) VALUES (?, ?)", (day, h)).rowcount == 1
            self.db.execute("INSERT OR IGNORE INTO daily (day) VALUES (?)", (day,))
        return day, new

    @staticmethod
    def source(ref):
        """Where a visitor came from: 'direct', 'internal', or a host / campaign label."""
        ref = ref.strip().lower() if isinstance(ref, str) else ""
        if "//" in ref:
            ref = ref.split("//", 1)[1]
        ref = re.split(r"[/?#]", ref, maxsplit=1)[0].split("@")[-1].split(":")[0]
        if ref.startswith("www."):
            ref = ref[4:]
        if not ref or not re.match(r"^[a-z0-9][a-z0-9._-]{0,59}$", ref):
            return "direct"
        return "internal" if any(ref == h or ref.endswith("." + h) for h in OWN_HOSTS) else ref

    def hit(self, who, ua, page, ref):
        page = page if isinstance(page, str) else ""
        page = page if GUIDE_RE.match(page) else PAGES.get(page)
        if not page or BOT_RE.search(ua or ""):
            return {}
        self.limit("hit", who)
        ref = self.source(ref)
        with self.lock:
            day, new = self._fresh(who, ua, "visit")
            self.db.execute("INSERT INTO views (day, page, ref, n) VALUES (?, ?, ?, 1) "
                            "ON CONFLICT (day, page, ref) DO UPDATE SET n = n + 1", (day, page, ref))
            if new:
                self.db.execute("UPDATE daily SET visitors = visitors + 1 WHERE day = ?", (day,))
            self.db.commit()
        return {}

    def download(self, who, ua):
        """Counts one download per visitor per day; programs and crawlers are not counted."""
        if BOT_RE.search(ua or ""):
            return
        try:
            self.limit("hit", who)
        except Fail:
            return
        with self.lock:
            day, new = self._fresh(who, ua, "download")
            if new:
                self.db.execute("UPDATE daily SET downloads = downloads + 1 WHERE day = ?", (day,))
            self.db.commit()

    def admin_stats(self, who, key):
        self.limit("admin", who)
        salt, _, want = os.environ.get("RC_ADMIN", "").partition(":")
        try:
            ok = bool(want) and hmac.compare_digest(pw_hash(key or "", bytes.fromhex(salt)), bytes.fromhex(want))
        except ValueError:
            ok = False
        if not ok:
            raise Fail(401, "Wrong password" if want else "The admin password is not set on the server")
        now = time.time()
        days = [time.strftime("%Y-%m-%d", time.gmtime(now - 86400 * i)) for i in range(30)]
        since = days[-1]
        views = dict(self.rows("SELECT day, SUM(n) FROM views WHERE day >= ? GROUP BY day", (since,)))
        daily = {d: (v, dl) for d, v, dl in self.rows("SELECT day, visitors, downloads FROM daily WHERE day >= ?", (since,))}
        total = self.one("SELECT COALESCE(SUM(visitors), 0), COALESCE(SUM(downloads), 0) FROM daily")
        return {
            "days": [{"day": d, "views": views.get(d, 0), "visitors": daily.get(d, (0, 0))[0],
                      "downloads": daily.get(d, (0, 0))[1]} for d in days],
            "total": {"views": self.one("SELECT COALESCE(SUM(n), 0) FROM views")[0], "visitors": total[0],
                      "downloads": total[1]},
            "sources": [{"ref": r, "views": n} for r, n in self.rows(
                "SELECT ref, SUM(n) FROM views WHERE day >= ? AND ref != 'internal' GROUP BY ref ORDER BY 2 DESC LIMIT 25",
                (since,))],
            "pages": [{"page": pg, "views": n} for pg, n in self.rows(
                "SELECT page, SUM(n) FROM views WHERE day >= ? GROUP BY page ORDER BY 2 DESC", (since,))],
            "accounts": {"all": self.one("SELECT COUNT(*) FROM users")[0],
                         "on_board": self.one("SELECT COUNT(*) FROM users WHERE points > 0")[0],
                         "supporters": self.one("SELECT COUNT(*) FROM users WHERE supporter != ''")[0],
                         "new_30d": self.one("SELECT COUNT(*) FROM users WHERE created >= ?", (now - 30 * 86400,))[0]},
            "version": VERSION,
        }

    def set_supporter(self, email, tier):
        tier = "" if tier == "none" else tier
        if tier and tier not in TIERS:
            raise ValueError("tier is one of: %s, none" % ", ".join(TIERS))
        with self.lock:
            n = self.db.execute("UPDATE users SET supporter = ? WHERE email = ?", (tier, email.strip().lower())).rowcount
            self.db.commit()
        return n == 1


def resend_mailer(key, sender):
    def send(to, subject, text):
        body = json.dumps({"from": sender, "to": [to], "subject": subject, "text": text}).encode()
        req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                              "User-Agent": "RetroCompanionServer"})
        try:
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as exc:
            sys.stderr.write("mail to %s failed: %s\n" % (to.split("@")[-1], exc))
    return send


def make_handler(svc):
    class Handler(BaseHTTPRequestHandler):
        server_version = "RetroCompanion/" + VERSION
        protocol_version = "HTTP/1.1"          # the proxy keeps connections open: every body must be read
        timeout = 60

        def who(self):
            fwd = self.headers.get("X-Forwarded-For", "")
            return fwd.split(",")[-1].strip() or self.client_address[0]

        def token(self):
            a = self.headers.get("Authorization", "")
            return a[7:].strip() if a.startswith("Bearer ") else ""

        def reply(self, status, obj):
            body = json.dumps(obj, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        @staticmethod
        def parse(raw):
            try:
                data = json.loads(raw or b"{}")
            except ValueError:
                raise Fail(400, "Bad request")
            if not isinstance(data, dict):
                raise Fail(400, "Bad request")
            return data

        def run(self, fn):
            try:
                self.reply(200, fn())
            except Fail as f:
                self.reply(f.status, {"error": f.message})
            except Exception as exc:
                sys.stderr.write("error on %s: %r\n" % (self.path.split("?")[0], exc))
                self.reply(500, {"error": "The server had a problem. Try again later"})

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/api/health":
                return self.run(lambda: {"ok": True, "version": VERSION, "games": len(svc.cat["games"]),
                                         "mail": svc.mail is not None})
            if path == "/api/leaderboard":
                m = re.search(r"(?:^|&)limit=(\d{1,3})(?:&|$)", query)
                return self.run(lambda: svc.leaderboard(self.who(), int(m.group(1)) if m else 50))
            if path == "/api/supporters":
                return self.run(lambda: svc.supporters(self.who()))
            if path == "/api/admin/stats":
                return self.run(lambda: svc.admin_stats(self.who(), self.token()))
            if path == "/api/download":
                try:
                    svc.download(self.who(), self.headers.get("User-Agent", ""))
                except Exception as exc:                # counting must never stand between a player and the file
                    sys.stderr.write("download count failed: %r\n" % (exc,))
                self.send_response(302)
                self.send_header("Location", DOWNLOAD)
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            path, who, tok = self.path.split("?")[0], self.who(), self.token()
            ua = self.headers.get("User-Agent", "")
            routes = {
                "/api/hit": lambda d: svc.hit(who, ua, d.get("page"), d.get("ref")),
                "/api/register": lambda d: svc.register(who, d.get("email"), d.get("password"), d.get("name")),
                "/api/login": lambda d: svc.login(who, d.get("email"), d.get("password")),
                "/api/logout": lambda d: svc.logout(tok),
                "/api/sync": lambda d: svc.sync(who, tok, d.get("state")),
                "/api/password": lambda d: svc.change_password(who, tok, d.get("old"), d.get("new")),
                "/api/reset/request": lambda d: svc.reset_request(who, d.get("email")),
                "/api/reset/confirm": lambda d: svc.reset_confirm(who, d.get("email"), d.get("code"), d.get("password")),
                "/api/account/delete": lambda d: svc.delete_account(who, tok, d.get("password")),
            }
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if not 0 <= n <= MAX_BODY:                 # unread bytes would spoil the kept-alive connection
                self.close_connection = True
                return self.reply(413 if n > 0 else 400, {"error": "Too much data" if n > 0 else "Bad request"})
            raw = self.rfile.read(n) if n else b""
            if path not in routes:
                return self.reply(404, {"error": "Not found"})
            self.run(lambda: routes[path](self.parse(raw)))

        def log_message(self, fmt, *args):          # no request log: it would hold addresses for nothing
            pass

    return Handler


def build(db_path, catalogue_path, port=0, mail=None):
    with open(catalogue_path, encoding="utf-8") as fh:
        svc = Service(db_path, json.load(fh), mail)
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(svc)), svc


def supporter_command(args):
    with open(os.environ.get("RC_CATALOGUE", os.path.join(HERE, "catalogue.json")), encoding="utf-8") as fh:
        svc = Service(os.environ.get("RC_DB", os.path.join(HERE, "retrocompanion.db")), json.load(fh))
    if len(args) == 2:
        try:
            ok = svc.set_supporter(args[0], args[1])
        except ValueError as e:
            sys.exit(str(e))
        print("%s is now: %s" % (args[0], args[1]) if ok else "No account with the email %s" % args[0])
        return
    if args:
        sys.exit("usage: app.py supporter [<email> <%s|none>]" % "|".join(TIERS))
    for email, name, tier in svc.rows("SELECT email, name, supporter FROM users WHERE supporter != '' ORDER BY email"):
        print("%-8s %s (%s)" % (tier, email, name))


def main():
    if sys.argv[1:2] == ["supporter"]:
        return supporter_command(sys.argv[2:])
    key = os.environ.get("RESEND_API_KEY", "").strip()
    mail = resend_mailer(key, os.environ.get("RC_MAIL_FROM", "Retro Companion <noreply@localhost>")) if key else None
    httpd, _ = build(os.environ.get("RC_DB", os.path.join(HERE, "retrocompanion.db")),
                     os.environ.get("RC_CATALOGUE", os.path.join(HERE, "catalogue.json")),
                     int(os.environ.get("RC_PORT", "8377")), mail)
    print("Retro Companion server %s on 127.0.0.1:%d, mail %s" % (VERSION, httpd.server_address[1], "on" if mail else "off"),
          flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
