"""The player's account on the Retro Companion server (see server/app.py).

Kept in the settings: the server address, the sign-in token, the email address and player
name. The password itself is never stored; it is sent once, over HTTPS, to get a token.
All calls here block: run them on a worker thread and post the result to the main one.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_SERVER = "https://retro.dieergames.hu"


class AccountError(Exception):
    def __init__(self, message, status=0):
        Exception.__init__(self, message)
        self.status = status


class Account:
    def __init__(self, settings):
        self.s = settings.setdefault("account", {})

    @property
    def server(self):
        return (os.environ.get("RC_SERVER") or self.s.get("server") or DEFAULT_SERVER).rstrip("/")

    @property
    def signed_in(self):
        return bool(self.s.get("token"))

    def call(self, method, path, data=None, timeout=15):
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"User-Agent": "RetroCompanion", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.s.get("token"):
            headers["Authorization"] = "Bearer " + self.s["token"]
        req = urllib.request.Request(self.server + path, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            try:
                msg = json.load(exc).get("error") or ""
            except Exception:
                msg = ""
            raise AccountError(msg or "The server answered with error %d" % exc.code, exc.code)
        except (OSError, ValueError) as exc:
            raise AccountError("The server could not be reached (%s)" % getattr(exc, "reason", exc))

    def keep(self, answer):
        """Remember a successful register / login / reset answer."""
        self.s["token"] = answer["token"]
        self.s["email"] = answer["user"]["email"]
        self.s["name"] = answer["user"]["name"]

    def forget(self):
        for k in ("token", "email", "name", "rank", "last_sync"):
            self.s.pop(k, None)
