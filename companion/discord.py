"""Discord Rich Presence: "Playing Dragon Warrior, Lv 9 · Kol" on the player's Discord profile.

Off until the player switches it on in the settings. It talks to the Discord program running
on the same computer through its local pipe (\\\\.\\pipe\\discord-ipc-0 .. 9); nothing goes
through a server of ours. The wire format (Discord's RPC documentation): a header of two
little-endian 32-bit numbers, opcode and length, then that many bytes of JSON. Opcode 0 is
the handshake {"v": 1, "client_id": ...}, opcode 1 a command such as SET_ACTIVITY.

It needs the ID of a Discord application (public, not a secret): APP_ID below, or the
settings key `discord_app`. Without one this module does nothing. Windows only.
"""
import json
import os
import queue
import struct
import sys
import threading
import time
import uuid

APP_ID = ""            # the Retro Companion application on Discord's developer portal, once it exists


def frame(op, payload):
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("<II", op, len(data)) + data


def activity(title, line, since):
    """The activity for a game: its title, one line about where the player is, and since when."""
    act = {"details": str(title)[:128], "timestamps": {"start": int(since)}}
    if line and len(str(line)) >= 2:
        act["state"] = str(line)[:128]
    return act


def command(act, pid=None):
    return {"cmd": "SET_ACTIVITY", "args": {"pid": pid or os.getpid(), "activity": act}, "nonce": str(uuid.uuid4())}


class Presence:
    """Keeps one activity up to date from a background thread, so a slow pipe never stalls the app."""
    GAP = 15.0             # Discord accepts an update every 15 seconds at most

    def __init__(self, app_id):
        self.app_id = str(app_id or "")
        self.q = queue.Queue()
        self.error = ""
        self._pipe = None
        self._last = None
        self._thread = None

    @property
    def usable(self):
        return bool(self.app_id) and sys.platform == "win32"

    def set(self, title=None, line="", since=None):
        """Show this activity (title None clears it). Returns at once."""
        if not self.usable:
            return
        want = None if title is None else (title, line, int(since or time.time()))
        if want == self._last:
            return
        self._last = want
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self.q.put(want)

    def _connect(self):
        for i in range(10):
            try:
                pipe = open(r"\\.\pipe\discord-ipc-%d" % i, "r+b", buffering=0)
            except OSError:
                continue
            pipe.write(frame(0, {"v": 1, "client_id": self.app_id}))
            self._reply(pipe)
            return pipe
        raise OSError("Discord is not running")

    @staticmethod
    def _reply(pipe):
        head = pipe.read(8)
        if len(head) == 8:
            op, n = struct.unpack("<II", head)
            return op, json.loads(pipe.read(n).decode("utf-8", "replace") or "{}")
        raise OSError("Discord closed the pipe")

    def _run(self):
        sent = 0.0
        while True:
            want = self.q.get()
            while not self.q.empty():               # only the newest one matters
                want = self.q.get()
            wait = self.GAP - (time.time() - sent)
            if wait > 0:
                time.sleep(wait)
                while not self.q.empty():
                    want = self.q.get()
            try:
                if self._pipe is None:
                    self._pipe = self._connect()
                self._pipe.write(frame(1, command(activity(*want) if want else None)))
                self._reply(self._pipe)
                self.error = ""
            except (OSError, ValueError) as exc:
                self.error = str(exc)
                try:
                    if self._pipe is not None:
                        self._pipe.close()
                except OSError:
                    pass
                self._pipe = None
            sent = time.time()
