"""Daily copy of the server database (SQLite online backup, safe while the server runs).
Keeps the last 14 copies in /var/backups/retrocompanion. Run by retrocompanion-backup.timer."""
import glob
import os
import sqlite3
import sys
import time

DB = os.environ.get("RC_DB", "/var/lib/retrocompanion/retrocompanion.db")
OUT = os.environ.get("RC_BACKUP_DIR", "/var/backups/retrocompanion")
KEEP = 14

if not os.path.exists(DB):
    sys.exit(0)
dst = os.path.join(OUT, time.strftime("retrocompanion-%Y%m%d.db"))
src, copy = sqlite3.connect(DB), sqlite3.connect(dst + ".tmp")
src.backup(copy)
try:                 # the visitor fingerprints of the day and their key do not go into a backup
    copy.execute("DELETE FROM seen")
    copy.execute("DELETE FROM meta WHERE key = 'salt'")
    copy.commit()
except sqlite3.OperationalError:
    pass
copy.close()
src.close()
os.replace(dst + ".tmp", dst)
for old in sorted(glob.glob(os.path.join(OUT, "retrocompanion-*.db")))[:-KEEP]:
    os.remove(old)
