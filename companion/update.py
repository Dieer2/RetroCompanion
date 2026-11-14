"""Updating the program from its release page on GitHub.

    check()      the newest release, if it is newer than this program
    download()   fetch its RetroCompanion.exe and compare it with the SHA-256 the release lists
    swap()       put the new program in the place of the running one
    restart()    start the new program

A running .exe cannot be overwritten on Windows, but it can be renamed: the running file
becomes RetroCompanion.old.exe, the new one takes its name, and the old one is deleted at
the next start (cleanup()). Installing works for the built program only (the .exe); run from
source, the program just tells where the new version is.

The check asks api.github.com for the latest release of the repository; nothing about the
player is sent. All calls block: run them on a worker thread.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "Dieer2/RetroCompanion"
API = "https://api.github.com/repos/%s/releases/latest" % REPO
PAGE = "https://github.com/%s/releases/latest" % REPO
ASSET = "RetroCompanion.exe"
# a download is taken only from the release files of this repository
TRUSTED = "https://github.com/%s/releases/download/" % REPO


class UpdateError(Exception):
    pass


def parse(version):
    """'v0.10' -> (0, 10). Anything that is not a version sorts lowest."""
    nums = re.findall(r"\d+", str(version).split("-")[0])
    return tuple(int(n) for n in nums[:4])


def newer(tag, current):
    return parse(tag) > parse(current)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "RetroCompanion", "Accept": "application/vnd.github+json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise UpdateError("GitHub answered with error %d" % exc.code)
    except (OSError, ValueError) as exc:
        raise UpdateError("GitHub could not be reached (%s)" % getattr(exc, "reason", exc))


def check(current, api=None, trusted=None):
    """None when this is the newest version, else a dict: version, notes, page, url, sums."""
    api = api or os.environ.get("RC_UPDATE_API") or API
    trusted = trusted or os.environ.get("RC_UPDATE_FILES") or TRUSTED
    try:
        with _get(api) as r:
            rel = json.load(r)
    except ValueError:
        raise UpdateError("GitHub sent an answer that could not be read")
    tag = str(rel.get("tag_name") or "")
    if not parse(tag) or not newer(tag, current):
        return None
    files = {a.get("name"): a.get("browser_download_url") or "" for a in rel.get("assets") or [] if isinstance(a, dict)}
    url, sums = files.get(ASSET, ""), files.get("SHA256.txt", "")
    ok = url.startswith(trusted) and sums.startswith(trusted)
    return {"version": tag.lstrip("vV"), "notes": str(rel.get("body") or "").strip(), "page": rel.get("html_url") or PAGE,
            "url": url if ok else "", "sums": sums if ok else ""}


def can_install(exe=None):
    """'' when the running program can replace itself, else why not."""
    if exe is None:
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return "This copy runs from the source code. Get the new version from the release page or with git"
        exe = sys.executable
    if not os.access(os.path.dirname(os.path.abspath(exe)), os.W_OK):
        return "The folder of the program cannot be written to. Download the new version from the release page"
    return ""


def download(info, dest, progress=None):
    """Fetch the new program to `dest` and check it against the release's SHA-256. Returns dest."""
    if not info.get("url") or not info.get("sums"):
        raise UpdateError("This release has no program file to download")
    with _get(info["sums"]) as r:
        text = r.read(4096).decode("utf-8", "replace")
    m = re.search(r"\b([0-9a-fA-F]{64})\b[ \t*]+%s\b" % re.escape(ASSET), text)
    if not m:
        raise UpdateError("The release does not list a checksum for the program")
    want = m.group(1).lower()
    h, done = hashlib.sha256(), 0
    try:
        with _get(info["url"], timeout=30) as r, open(dest, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except OSError as exc:
        _remove(dest)
        raise UpdateError("The download failed (%s)" % exc)
    if h.hexdigest() != want or done < 1024:
        _remove(dest)
        raise UpdateError("The downloaded file does not match the checksum of the release. Nothing was changed")
    return dest


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def paths(exe):
    """(where the download goes, where the running program is moved to)."""
    base, ext = os.path.splitext(os.path.abspath(exe))
    return base + ".new" + ext, base + ".old" + ext


def swap(exe, new):
    """The running program steps aside and the new one takes its name. Undone if the second step fails."""
    exe = os.path.abspath(exe)
    old = paths(exe)[1]
    _remove(old)
    try:
        os.rename(exe, old)
    except OSError as exc:
        raise UpdateError("The program file could not be moved aside (%s)" % exc)
    try:
        os.rename(new, exe)
    except OSError as exc:
        os.rename(old, exe)
        raise UpdateError("The new version could not be put in place (%s)" % exc)
    return exe


def cleanup(exe=None):
    """Delete what an earlier update left behind. Called at start."""
    if exe is None:
        if not getattr(sys, "frozen", False):
            return
        exe = sys.executable
    for p in paths(exe):
        _remove(p)


def restart(exe=None):
    """Start the program again, as a process of its own."""
    exe = exe or sys.executable
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"      # the new program unpacks itself afresh
    env.pop("_MEIPASS2", None)
    subprocess.Popen([exe], env=env, close_fds=True, cwd=os.path.dirname(os.path.abspath(exe)))
