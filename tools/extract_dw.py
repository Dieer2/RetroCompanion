"""Reads Dragon Warrior's tables out of a ROM and saves them where the app keeps them, or
prints a summary for checking.   python tools/extract_dw.py <rom.nes> [--save]

The app does the same itself when the player chooses the ROM in the library; the reading
code lives in games/dragon_warrior.py (extract)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import games.dragon_warrior as DW            # noqa: E402

rom = sys.argv[1]
d = DW.extract(open(rom, "rb").read())
print("enemies", len(d["en"]), "maps", len(d["maps"]), "chests", len(d["chests"]), "links", len(d["links"]),
      "spell costs", d["cost"])
if "--save" in sys.argv:
    err = DW.PLUGIN.prepare(rom)
    print(err or "saved to " + DW.DATA_FILE)
