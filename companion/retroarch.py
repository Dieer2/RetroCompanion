"""RetroArch access: the UDP network command interface, finding the install, launching content.

Formats follow the libretro docs (Network Control Interface, Command-Line Interface):
  GET_STATUS  ->  "GET_STATUS PAUSED|PLAYING system_id,game_basename,crc32=XXXXXXXX" or "GET_STATUS CONTENTLESS"
  retroarch -L <core> <content> [--appendconfig <file>]
"""
import os
import shutil
import socket
import subprocess
import sys

DEFAULT_PORT = 55355


class RetroArch:
    def __init__(self, host="127.0.0.1", port=DEFAULT_PORT):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd = "READ_CORE_MEMORY"
        self.bad = set()          # optional ranges this core cannot read

    def ask(self, text, timeout=0.4):
        try:
            self.sock.settimeout(0.0)      # drop stale replies
            try:
                while True:
                    self.sock.recvfrom(65535)
            except (BlockingIOError, OSError):
                pass
            self.sock.settimeout(timeout)
            self.sock.sendto(text.encode("ascii"), self.addr)
            data, _ = self.sock.recvfrom(65535)
            return data.decode("utf-8", "replace").strip()
        except (socket.timeout, OSError):
            return None

    def tell(self, text):
        """Send a command that has no reply (SHOW_MSG <text>, SCREENSHOT). True when it was sent."""
        try:
            self.sock.sendto(text.encode("utf-8"), self.addr)
            return True
        except OSError:
            return False

    def status(self):
        """None if RetroArch does not answer, else dict(state, system, name, crc)."""
        resp = self.ask("GET_STATUS")
        if not resp or not resp.startswith("GET_STATUS"):
            return None
        rest = resp[len("GET_STATUS"):].strip()
        if rest.upper().startswith("CONTENTLESS") or not rest:
            return {"state": "CONTENTLESS", "system": "", "name": "", "crc": ""}
        state, _, info = rest.partition(" ")
        crc = ""
        if ",crc32=" in info:
            info, _, crc = info.rpartition(",crc32=")
        system, _, name = info.partition(",")
        return {"state": state.upper(), "system": system.strip(), "name": name.strip(),
                "crc": crc.strip().lower().lstrip("0x").rjust(8, "0") if crc.strip() else ""}

    def _read(self, cmd, addr, n):
        resp = self.ask("%s %x %d" % (cmd, addr, n))
        if resp is None:
            return None, "timeout"
        parts = resp.split()
        if len(parts) < 3 or parts[0] != cmd:
            return None, "bad reply"
        if parts[2] == "-1":
            return None, " ".join(parts[3:]) or "no data"
        try:
            data = bytes(int(p, 16) for p in parts[2:])
        except ValueError:
            return None, "bad reply"
        if len(data) < n:
            return None, "short reply (%d bytes)" % len(data)
        return data, None

    def read(self, addr, n):
        data, err = self._read(self.cmd, addr, n)
        if data is None and err != "timeout":
            other = "READ_CORE_RAM" if self.cmd == "READ_CORE_MEMORY" else "READ_CORE_MEMORY"
            data2, _ = self._read(other, addr, n)
            if data2 is not None:
                self.cmd = other
                return data2, None
        return data, err

    def read_blocks(self, ranges):
        """ranges: (address, length, required). Returns (list of bytes-or-None, error-or-None)."""
        out = []
        for addr, n, required in ranges:
            if not required and (addr, n) in self.bad:
                out.append(None)
                continue
            data, err = self.read(addr, n)
            if data is None:
                if required:
                    return None, err
                if err != "timeout":
                    self.bad.add((addr, n))
            out.append(data)
        return out, None


# -- install discovery and launching -------------------------------------------
def find_install():
    cands = []
    if sys.platform == "win32":
        for base in (os.environ.get("APPDATA", ""), os.environ.get("ProgramFiles", ""),
                     os.environ.get("ProgramFiles(x86)", ""), "C:\\", os.path.expanduser("~")):
            if base:
                for sub in ("RetroArch", "RetroArch-Win64", os.path.join("Steam", "steamapps", "common", "RetroArch")):
                    cands.append(os.path.join(base, sub, "retroarch.exe"))
    elif sys.platform == "darwin":
        cands.append("/Applications/RetroArch.app/Contents/MacOS/RetroArch")
    for c in cands:
        if os.path.isfile(c):
            return c
    return shutil.which("retroarch") or ""


def _core_dirs(exe):
    d = [os.path.join(os.path.dirname(exe), "cores")] if exe else []
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        d.append(os.path.join(home, "Library", "Application Support", "RetroArch", "cores"))
    elif sys.platform != "win32":
        d += [os.path.join(home, ".config", "retroarch", "cores"), "/usr/lib/libretro",
              "/usr/lib/x86_64-linux-gnu/libretro"]
    return d


def find_core(exe, names):
    """First installed core among `names` (e.g. 'mesen'). Returns (name, path) or (None, None)."""
    ext = ".dll" if sys.platform == "win32" else (".dylib" if sys.platform == "darwin" else ".so")
    for name in names:
        for d in _core_dirs(exe):
            p = os.path.join(d, name + "_libretro" + ext)
            if os.path.isfile(p):
                return name, p
    return None, None


def config_path(exe):
    cands = []
    if exe:
        cands.append(os.path.join(os.path.dirname(exe), "retroarch.cfg"))
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        cands.append(os.path.join(os.environ.get("APPDATA", ""), "RetroArch", "retroarch.cfg"))
    elif sys.platform == "darwin":
        cands.append(os.path.join(home, "Library", "Application Support", "RetroArch", "config", "retroarch.cfg"))
    else:
        cands.append(os.path.join(home, ".config", "retroarch", "retroarch.cfg"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return ""


def config_value(exe, key):
    """Read one value from retroarch.cfg (read-only). None if unknown."""
    p = config_path(exe)
    if not p:
        return None
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"')
    except OSError:
        pass
    return None


# -- where RetroArch keeps its saves --------------------------------------------
def _folder(exe, key, default):
    """A directory setting of retroarch.cfg as a real path (":" stands for RetroArch's own folder)."""
    base = os.path.dirname(os.path.abspath(exe)) if exe else ""
    v = (config_value(exe, key) or "").strip()
    if v in ("", "default"):
        v = ":" + os.sep + default
    if v.startswith(":"):
        v = os.path.join(base, v[1:].lstrip("\\/"))
    return os.path.expanduser(v)


def _files(folder, depth=1):
    """The files of a folder and of its sub-folders (RetroArch may sort saves by core or by system)."""
    try:
        with os.scandir(folder) as it:
            for e in it:
                if e.is_file():
                    yield e
                elif depth and e.is_dir():
                    for f in _files(e.path, depth - 1):
                        yield f
    except OSError:
        return


def save_files(exe, content, rom=""):
    """What RetroArch has saved for a game whose content name is `content` (the file name without
    its extension): {"states": [(slot, time)], newest first, "battery": time or None}.
    A slot is a number (0 for the plain .state file) or "auto". Read-only: it only looks at file times."""
    out = {"states": [], "battery": None}
    if not content:
        return out
    here = os.path.dirname(rom) if rom else ""
    for key, default, in_content, kind in (("savestate_directory", "states", "savestates_in_content_dir", "state"),
                                           ("savefile_directory", "saves", "savefiles_in_content_dir", "battery")):
        folders = [_folder(exe, key, default)]
        if here and config_value(exe, in_content) == "true":
            folders.append(here)
        for folder in folders:
            for f in _files(folder, 1 if folder != here else 0):
                name = f.name
                if not name.startswith(content + "."):
                    continue
                tail = name[len(content) + 1:]
                try:
                    when = f.stat().st_mtime
                except OSError:
                    continue
                if kind == "battery":
                    if tail in ("srm", "sav"):
                        out["battery"] = max(out["battery"] or 0, when)
                elif tail == "state":
                    out["states"].append((0, when))
                elif tail == "state.auto":
                    out["states"].append(("auto", when))
                elif tail.startswith("state") and tail[5:].isdigit():
                    out["states"].append((int(tail[5:]), when))
    out["states"].sort(key=lambda s: -s[1])
    return out


def launch(exe, core_path, rom, port=DEFAULT_PORT):
    """Start RetroArch with a core and content. Network commands are switched on for this
    session through an appended config file, so the user's own retroarch.cfg is not edited here."""
    extra = os.path.join(os.path.expanduser("~"), ".retro_companion_retroarch.cfg")
    with open(extra, "w", encoding="utf-8") as fh:
        fh.write('network_cmd_enable = "true"\nnetwork_cmd_port = "%d"\n' % port)
    args = [exe, "-L", core_path, rom, "--appendconfig", extra]
    return subprocess.Popen(args, cwd=os.path.dirname(exe) or None)
