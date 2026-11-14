# -*- coding: utf-8 -*-
"""Dragon Warrior (NES, 1989, US) plugin for Retro Companion.

The game's tables (enemy stats, map layouts, chests, stair links, encounter zones, spell
costs) are read from the player's own ROM by extract(); their layout follows the public
disassembly by nmikstas. Nothing from the game is in this file. Walkthrough facts are checked against StrategyWiki, Gamer Corner Guides and
Dragon's Den. Memory addresses: Data Crystal RAM map and the same disassembly.
"""
import hashlib
import heapq
import json
import os
import re

from companion.plugin import GamePlugin

# --------------------------------------------------------------------------
# THE GAME'S OWN TABLES: read from the player's copy, never shipped
# --------------------------------------------------------------------------
# Enemy stats, maps, chests, stair links, encounter zones and spell costs come out of the
# player's own ROM the first time it is chosen (extract() below; table addresses from the
# nmikstas disassembly, PRG0) and are kept in DATA_FILE on that computer. FINGERPRINT is the
# SHA-256 of what extract() makes from Dragon Warrior (USA) PRG0; anything else is refused,
# since the table addresses are only known for that release.
DATA_DIR = os.environ.get("RC_DATA_DIR") or os.path.join(os.path.expanduser("~"), "RetroCompanion", "data")
DATA_FILE = os.path.join(DATA_DIR, "dragon_warrior.json")
FINGERPRINT = "d03621c52bc56fc88ab0e0b70a220a5b8dedc7149bd8c49c26d1bedce164c12e"
DATA = None          # the tables, once loaded


def _canonical(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def extract(rom):
    """The game's tables from ROM bytes (with or without the 16-byte iNES header)."""
    d = rom[16:] if rom[:4] == b"NES\x1a" else rom
    if len(d) < 0x10000:
        raise ValueError("too small for Dragon Warrior")
    b0 = lambda a: a - 0x8000                 # bank 0 (maps)
    b1 = lambda a: a - 0x8000 + 0x4000        # bank 1 (enemies, chests, spell costs)
    out = {"en": [list(d[b1(0x9E4B) + 16 * i: b1(0x9E4B) + 16 * i + 8]) for i in range(40)]}
    maps = {}
    for m in range(2, 0x1E):
        o = b0(0x801A) + 5 * m
        ptr, w, h, border = d[o] | d[o + 1] << 8, d[o + 2] + 1, d[o + 3] + 1, d[o + 4]
        stride, base, rows = (w + 1) // 2, b0(ptr), []
        # the game's tile fetch (CPU $ACCA): 4 bits per tile below map 0x0C, 3 bits from there;
        # its tile-set choice ($B020): the dungeon set only from map 0x0F
        mask = 0x0F if m < 0x0C else 0x07
        for y in range(h):
            row = ""
            for x in range(w):
                b = d[base + y * stride + x // 2]
                row += "%x" % (((b >> 4) if x % 2 == 0 else (b & 15)) & mask)
            rows.append(row)
        maps[m] = dict(w=w, h=h, b=border, dun=int(m >= 0x0F), rows=rows)
    out["maps"] = maps
    pt, world = b0(0xA653), []
    for y in range(120):                        # the overworld is run-length coded, row by row
        p, row = b0(d[pt + 2 * y] | d[pt + 2 * y + 1] << 8), ""
        while len(row) < 120:
            b = d[p]
            p += 1
            row += ("%x" % (b >> 4)) * ((b & 15) + 1)
        world.append(row[:120])
    out["world"] = world
    chests, o = [], b1(0x9DCD)
    while 1 <= d[o] <= 0x1D and len(chests) < 40:
        chests.append(list(d[o:o + 4]))
        o += 4
    out["chests"] = chests
    n, a = 51, 0xF3C8
    out["links"] = [list(d[a + 3 * i:a + 3 * i + 3]) + list(d[a + 3 * n + 3 * i:a + 3 * n + 3 * i + 3]) for i in range(n)]
    out["grid"] = [[(d[0xF522 + 4 * y + x // 2] >> (4 if x % 2 == 0 else 0)) & 15 for x in range(8)] for y in range(8)]
    out["cave"] = list(d[0xF542:0xF542 + 13])
    out["groups"] = [list(d[0xF54F + 5 * i:0xF54F + 5 * i + 5]) for i in range(20)]
    out["cost"] = list(d[b0(0x9D53):b0(0x9D53) + 10])
    return json.loads(json.dumps(out))         # same shape as after a round trip through the file


def load_data():
    """The tables saved earlier on this computer, or None."""
    global DATA
    try:
        with open(DATA_FILE, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        return None
    if hashlib.sha256(_canonical(d).encode("utf-8")).hexdigest() != FINGERPRINT:
        return None
    DATA = d
    return d

TANTEGEL = (43, 43)  # world-map coordinates; the game measures from here (Gwaelin's Love)

MAPS = {
    0x01: "Alefgard (overworld)", 0x02: "Charlock Castle 1F", 0x03: "Hauksness (ruins)",
    0x04: "Tantegel Castle", 0x05: "Tantegel throne room", 0x06: "Charlock B7 (bottom)",
    0x07: "Kol", 0x08: "Brecconary", 0x09: "Garinham", 0x0A: "Cantlin", 0x0B: "Rimuldar",
    0x0C: "Tantegel cellar", 0x0D: "Northern Shrine (Staff of Rain)",
    0x0E: "Southern Shrine (Rainbow Drop)",
    0x0F: "Charlock B1", 0x10: "Charlock B2", 0x11: "Charlock B3", 0x12: "Charlock B4",
    0x13: "Charlock B5", 0x14: "Charlock B6", 0x15: "Swamp Cave",
    0x16: "Mountain Cave B1", 0x17: "Mountain Cave B2",
    0x18: "Garin's Grave B1", 0x19: "Garin's Grave B2", 0x1A: "Garin's Grave B3",
    0x1B: "Garin's Grave B4", 0x1C: "Erdrick's Cave B1", 0x1D: "Erdrick's Cave B2",
}

WEAPONS = ["no weapon", "Bamboo Pole", "Club", "Copper Sword", "Hand Axe", "Broad Sword", "Flame Sword", "Erdrick's Sword"]
ARMORS = ["no armor", "Clothes", "Leather Armor", "Chain Mail", "Half Plate", "Full Plate", "Magic Armor", "Erdrick's Armor"]
SHIELDS = ["no shield", "Small Shield", "Large Shield", "Silver Shield"]
ITEMS = {1: "Torch", 2: "Fairy Water", 3: "Wings", 4: "Dragon's Scale", 5: "Fairy Flute",
         6: "Fighter's Ring", 7: "Erdrick's Token", 8: "Gwaelin's Love", 9: "Cursed Belt",
         10: "Silver Harp", 11: "Death Necklace", 12: "Stones of Sunlight", 13: "Staff of Rain",
         14: "Rainbow Drop"}
# What the gear is worth. Checked against the game's own tables in the owner's ROM (2026-11-14):
# weapon, armor and shield bonuses at PRG offset 0x19CF / 0x19D7 / 0x19DF, shop prices at 0x1947
# (16-bit each); a shop buys an item back for half its price.
ATK_BONUS = [0, 2, 4, 10, 15, 20, 28, 40]
DEF_ARMOR = [0, 2, 4, 10, 16, 24, 24, 28]
DEF_SHIELD = [0, 4, 10, 20]
PRICE = {"Bamboo Pole": 10, "Club": 60, "Copper Sword": 180, "Hand Axe": 560, "Broad Sword": 1500, "Flame Sword": 9800,
         "Erdrick's Sword": 2, "Clothes": 20, "Leather Armor": 70, "Chain Mail": 300, "Half Plate": 1000,
         "Full Plate": 3000, "Magic Armor": 7700, "Erdrick's Armor": 2, "Small Shield": 90, "Large Shield": 800,
         "Silver Shield": 14800, "Herb": 24, "Torch": 8, "Fairy Water": 38, "Wings": 70, "Dragon's Scale": 20,
         "Fighter's Ring": 30, "Cursed Belt": 360, "Death Necklace": 2400}
# who sells what (the same lists as the town notes below)
SHOPS = {
    "Brecconary": ["Bamboo Pole", "Club", "Copper Sword", "Clothes", "Leather Armor", "Small Shield", "Herb", "Torch",
                   "Dragon's Scale", "Fairy Water"],
    "Garinham": ["Club", "Copper Sword", "Hand Axe", "Leather Armor", "Chain Mail", "Half Plate", "Large Shield", "Herb",
                 "Torch", "Dragon's Scale"],
    "Kol": ["Copper Sword", "Hand Axe", "Half Plate", "Full Plate", "Small Shield", "Herb", "Torch", "Dragon's Scale", "Wings"],
    "Rimuldar": ["Copper Sword", "Hand Axe", "Broad Sword", "Half Plate", "Full Plate", "Magic Armor"],
    "Cantlin": ["Flame Sword", "Silver Shield", "Broad Sword", "Full Plate", "Magic Armor", "Hand Axe", "Large Shield",
                "Chain Mail", "Fairy Water", "Herb", "Torch", "Dragon's Scale", "Wings"],
}
# what a thing does, beyond its numbers
ITEM_NOTES = {
    "Magic Armor": ["Restores 1 HP every 4 steps", "Takes a third off HURT and HURTMORE damage"],
    "Erdrick's Armor": ["Restores 1 HP every step", "No damage from swamp and barriers",
                        "Takes a third off fire and HURT damage", "Buried in Hauksness: SEARCH on the tree tile after the Axe Knight"],
    "Erdrick's Sword": ["The strongest weapon. In a chest in Charlock, in the closed middle room of B2"],
    "Herb": ["Restores 23 to 30 HP", "You can carry 6"],
    "Magic Key": ["Opens one locked door, then it is gone", "You can carry 6",
                  "53 G in Rimuldar, 85 G in Tantegel, 98 G in Cantlin"],
    "Torch": ["Lights the tiles next to you in a cave", "RADIANT (level 9) lights more"],
    "Fairy Water": ["Keeps weak monsters away for a while, like REPEL"],
    "Wings": ["Takes you back to Tantegel Castle", "Does not work inside caves"],
    "Dragon's Scale": ["Defense +2 once you USE it", "Wear it right after buying"],
    "Fairy Flute": ["Puts the Golem at Cantlin's gate to sleep (use it in the battle)",
                    "Found in Kol: SEARCH 4 tiles south of the bath"],
    "Fighter's Ring": ["No effect in the NES version (a known bug)", "Chest in the Mountain Cave, B2"],
    "Erdrick's Token": ["Proof that you are Erdrick's heir", "One of the three things the Southern Shrine asks for",
                        "Found in the swamp 70 south, 40 east of Tantegel"],
    "Gwaelin's Love": ["Tells how far you are from Tantegel and the XP to your next level", "From the princess, once she is home"],
    "Cursed Belt": ["Cursed: do not use it", "A curse is lifted in Brecconary"],
    "Death Necklace": ["Cursed: do not use it", "A curse is lifted in Brecconary"],
    "Silver Harp": ["Played, it calls a monster", "The old man of the Northern Shrine trades the Staff of Rain for it",
                    "Chest in Garin's Grave"],
    "Stones of Sunlight": ["One of the three things the Southern Shrine asks for", "Chest in the cellar of Tantegel Castle"],
    "Staff of Rain": ["One of the three things the Southern Shrine asks for", "From the Northern Shrine, for the Silver Harp"],
    "Rainbow Drop": ["Used at the tip of the peninsula north-west of Rimuldar, it makes the bridge to Charlock",
                     "From the Southern Shrine"],
}
SPELL_NOTES = {
    "HEAL": "Restores 10 to 17 HP", "HURT": "5 to 12 damage", "SLEEP": "Puts the enemy to sleep",
    "RADIANT": "Lights a cave, wider than a Torch; it fades as you walk", "STOPSPELL": "Stops the enemy's spells",
    "OUTSIDE": "Takes you out of a cave", "RETURN": "Takes you back to Tantegel Castle",
    "REPEL": "Keeps weak monsters away for a while", "HEALMORE": "Restores 85 to 100 HP", "HURTMORE": "58 to 65 damage",
}


def item_tips(g):
    """name -> lines: what every weapon, armor, shield, item and spell does, set against what the hero has."""
    tips = {}

    def money(name, lines):
        price = PRICE.get(name)
        towns = [t for t, stock in SHOPS.items() if name in stock]
        if towns:
            lines.append("%d G · sold in %s" % (price, ", ".join(towns)))
            if g is not None:
                lines.append("You have %d G: %s" % (g.gold, "enough" if g.gold >= price else "%d G short" % (price - g.gold)))
        if price:
            lines.append("A shop pays %d G for it" % (price // 2))

    for names, table, stat, mine in ((WEAPONS, ATK_BONUS, "Attack", None if g is None else g.weapon),
                                     (ARMORS, DEF_ARMOR, "Defense", None if g is None else g.armor),
                                     (SHIELDS, DEF_SHIELD, "Defense", None if g is None else g.shield)):
        kind = {id(WEAPONS): "Weapon", id(ARMORS): "Armor", id(SHIELDS): "Shield"}[id(names)]
        for i, name in enumerate(names):
            if i == 0:
                tips[name] = ["Nothing in this slot: %s +0" % stat.lower()]
                continue
            lines = ["%s · %s +%d" % (kind, stat.lower(), table[i])]
            if mine is not None:
                d = table[i] - table[mine]
                lines.append("You are wearing it" if i == mine else "%s%d %s against your %s (+%d)" % (
                    "+" if d >= 0 else "", d, stat.lower(), names[mine] if mine else "empty slot", table[mine]))
            lines += ITEM_NOTES.get(name, [])
            money(name, lines)
            tips[name] = lines
    for name in ["Herb", "Magic Key"] + list(ITEMS.values()):
        lines = list(ITEM_NOTES.get(name, []))
        if g is not None:
            have = {"Herb": g.herbs, "Magic Key": g.keys}.get(name)
            if have is not None:
                lines.append("You carry %d" % have)
            elif name in [ITEMS[i] for i in g.items if i in ITEMS]:
                lines.append("You carry one")
        money(name, lines)
        tips[name] = lines
    cost = DATA["cost"] if DATA else [4, 2, 2, 3, 2, 6, 8, 2, 10, 5]
    level = {v: k for k, v in SPELLS.items()}
    for i, name in enumerate(SPELL_ORDER):
        lines = ["Spell · %d MP · learned at level %d" % (cost[i], level[name]), SPELL_NOTES[name]]
        if g is not None:
            lines.append("You know it: %d MP is enough for %d" % (g.mp, g.mp // cost[i]) if name in g.spells
                         else "Not learned yet")
        tips[name] = lines
    return tips


ENEMIES = ("Slime,Red Slime,Drakee,Ghost,Magician,Magidrakee,Scorpion,Druin,Poltergeist,Droll,Drakeema,"
           "Skeleton,Warlock,Metal Scorpion,Wolf,Wraith,Metal Slime,Specter,Wolflord,Druinlord,Drollmagi,"
           "Wyvern,Rogue Scorpion,Wraith Knight,Golem,Goldman,Knight,Magiwyvern,Demon Knight,Werewolf,"
           "Green Dragon,Starwyvern,Wizard,Axe Knight,Blue Dragon,Stoneman,Armored Knight,Red Dragon,"
           "Dragonlord,Dragonlord (true form)").split(",")
CHEST = {2: "Herb", 3: "Magic Key", 4: "Torch", 6: "Wings", 9: "Fighter's Ring", 0x0C: "Cursed Belt",
         0x0D: "Silver Harp", 0x0E: "Death Necklace or gold", 0x0F: "Stones of Sunlight",
         0x10: "Staff of Rain", 0x11: "Erdrick's Sword", 0x12: "5-20 G", 0x13: "6-13 G",
         0x14: "10-17 G", 0x15: "500-755 G", 0x16: "120 G", 0x17: "Erdrick's Tablet"}

# Total XP needed for levels 1..30 (Gamer Corner Guides level table; the game's own table
# at $F34B agrees, level 30 = 65,535 is the cap)
XP_TABLE = [0, 7, 23, 47, 110, 220, 450, 800, 1300, 2000, 2900, 4000, 5500, 7500,
            10000, 13000, 16000, 19000, 22000, 26000, 30000, 34000, 38000, 42000,
            46000, 50000, 54000, 58000, 62000, 65535]
SPELLS = {3: "HEAL", 4: "HURT", 7: "SLEEP", 9: "RADIANT", 10: "STOPSPELL", 12: "OUTSIDE",
          13: "RETURN", 15: "REPEL", 17: "HEALMORE", 19: "HURTMORE"}
SPELL_ORDER = ["HEAL", "HURT", "SLEEP", "RADIANT", "STOPSPELL", "OUTSIDE", "RETURN", "REPEL",
               "HEALMORE", "HURTMORE"]

# Notes for the map you are standing on (shops, hints)
LOC = {
    0x05: ["Chests: use TAKE (120 G, Torch, Magic Key).",
           "Door: use DOOR (spends a key). On the stairs: use STAIRS.",
           "SAVING: only here, by talking to the king."],
    0x04: ["Old man right of the entrance: restores your MP for free.",
           "Behind the locked door (back area): key shop, 85 G each.",
           "Stones of Sunlight: from the girl next to the key shop walk down along the east side of the "
           "castle to the water, one more tile right, around the water to the cellar stairs (SE corner)."],
    0x0C: ["The chest holds the Stones of Sunlight (TAKE)."],
    0x08: ["Weapons: Bamboo Pole 10 · Club 60 · Copper Sword 180 · Clothes 20 · Leather Armor 70 · Small Shield 90",
           "Items (SE corner): Herb 24 · Torch 8 · Dragon's Scale 20",
           "Inn: 6 G. Behind the locked NE door: Fairy Water 38 G.",
           "The curse remover lives here (Cursed Belt / Death Necklace)."],
    0x09: ["Shop: Club 60 · Copper Sword 180 · Hand Axe 560 · Leather Armor 70 · Chain Mail 300 · Half Plate 1000 · Large Shield 800",
           "Items: Herb 24 · Torch 8 · Dragon's Scale 20. Inn: 25 G.",
           "Large north building (needs a key): inside, walk through the dark wall to get behind the "
           "building; the stairs at the top lead to Garin's Grave (Silver Harp)."],
    0x07: ["Shop: Copper Sword 180 · Hand Axe 560 · Half Plate 1000 · Full Plate 3000 · Small Shield 90",
           "Items: Herb 24 · Torch 8 · Dragon's Scale 20 · Wings 70. Inn: 20 G.",
           "Fairy Flute: SEARCH exactly 4 tiles south of the bath (no key needed)."],
    0x0B: ["Shop: Copper Sword 180 · Hand Axe 560 · Broad Sword 1500 · Half Plate 1000 · Full Plate 3000 · Magic Armor 7700",
           "KEY SHOP: 53 G each, max 6. It is the NW hut; reach it by walking around OUTSIDE the moat.",
           "Inn: 55 G. The man behind the inn's locked door tells where the Fairy Flute is (optional)."],
    0x0A: ["Behind the locked NE door: Flame Sword 9800 · Silver Shield 14800, and a key shop (98 G each).",
           "Other shops: Broad Sword 1500 · Full Plate 3000 · Magic Armor 7700 · Hand Axe 560 · Large Shield 800 · Chain Mail 300",
           "Fairy Water 38 · Herb 24 · Torch 8 · Dragon's Scale 20 · Wings 70. Inn: 100 G.",
           "South part: behind locked doors and damaging barriers (15 HP per step) a sage tells where the Token is."],
    0x03: ["Strong monsters! The goal is the tree tile on the EAST side, behind the swamp-covered old shop.",
           "Stepping on it starts the Axe Knight fight (no running): cast STOPSPELL until it lands "
           "(he casts SLEEP), then FIGHT + HEALMORE.",
           "After winning do NOT step off the tile: SEARCH to get Erdrick's Armor."],
    0x0D: ["The old man trades the chest (Staff of Rain) for the Silver Harp."],
    0x0E: ["Needs Erdrick's Token + Stones of Sunlight + Staff of Rain. You get the Rainbow Drop."],
    0x15: ["North-south tunnel between the Kol area and Rimuldar. Light: Torch or RADIANT.",
           "The side branch hides a fixed Green Dragon fight; behind it a locked door and the princess.",
           "If you are still weak, skip the branch and go straight to the south exit."],
    0x16: ["Optional cave. Chest in the NE corridor: Herb.",
           "Only the MIDDLE stairs lead to all the treasure below; the two corner stairs are dead ends."],
    0x17: ["Fighter's Ring chest in the NW pair (it has no effect in the NES version: a known bug).",
           "The chest on the SW loop: Death Necklace or gold. Do NOT use the necklace (curse); it sells for 1200 G.",
           "Warlock, Drakeema: STOPSPELL."],
    0x18: ["Three chests in the north alcove (Herb + a little gold).",
           "Goal: the locked door in the bottom right, then the south corridor to the stairs in the SW corner."],
    0x19: ["Five stairs down. Follow the route line: only one of them leads on to the harp.",
           "Two others reach the Cursed Belt chest (do not use it; sells for 180 G); the rest are dead ends."],
    0x1A: ["Wraith Knight heals itself; Specter casts SLEEP: use STOPSPELL.",
           "The Silver Harp chest is reached through the small B4 floor (down, across, up again)."],
    0x1B: ["Tiny floor: cross to the other stairs UP. They lead to the Silver Harp chamber. Then cast OUTSIDE."],
    0x1C: ["No monsters. Use a Torch (ITEM) or RADIANT. Find the stairs down."],
    0x1D: ["The chest holds Erdrick's Tablet (TAKE): the story of your quest. Nothing else here."],
    0x02: ["The two visible stairs (behind locked doors and barriers) are false paths.",
           "The real one: stand BEHIND the throne and SEARCH. A hidden staircase appears."],
    0x0F: ["Follow the route line down to B2."],
    0x10: ["The chest in the middle room is Erdrick's Sword. It can only be reached from B4 on the way back up."],
    0x11: ["The stairs going up from here are false paths that loop into each other."],
    0x12: ["FORK: one staircase goes back UP toward Erdrick's Sword, another goes DOWN toward the Dragonlord.",
           "A third one is a trap: an endless corridor. Follow the route line."],
    0x13: ["Follow the outer corridor to the stairs down."],
    0x14: ["One staircase here loops back to this floor. Follow the route line to the bottom floor."],
    0x06: ["Treasure room in the middle: Herb x2, 500-755 G, Wings, Magic Key, Cursed Belt (all optional).",
           "The Dragonlord sits in the throne room at the bottom. Answer NO to his offer! (YES ends the game.)"],
}

# Steps. target = (name, x, y) on the WORLD map (straight-line compass);
# goal = ("map", id) or ("tile", map, x, y) for the walking route.
STEPS = [
    dict(id="throne", ch="1 · Setting out", title="Throne room: chests, key, stairs",
         goal=("tile", 0x05, 8, 8),
         lines=["Listen to the king, then TAKE all three chests: 120 G, Torch, Magic Key.",
                "At the door use DOOR (the key is spent); on the stairs use STAIRS.",
                "You can only save by talking to the king. Come back here to save."]),
    dict(id="brecc", ch="1 · Setting out", title="Brecconary: first equipment",
         target=("Brecconary", 48, 41), goal=("map", 0x08),
         lines=["Leave Tantegel; the town is a few steps east.",
                "Weapon shop: Club (60 G) + Clothes (20 G).",
                "Item shop (SE corner): Dragon's Scale (20 G). Use it from the ITEM menu to wear it.",
                "That leaves 20 G for the inn (6 G a night)."]),
    dict(id="lv3", ch="1 · Setting out", title="Train to level 3 (HEAL)", rec=3,
         lines=["Stay close to Tantegel and Brecconary: Slime, Red Slime, Drakee.",
                "Do NOT cross a bridge yet. Monsters get stronger past every bridge.",
                "Level 3: HEAL. From now on the old man right of Tantegel's entrance refills your MP for free."]),
    dict(id="tablet", ch="1 · Setting out", title="Erdrick's Cave: the tablet (optional)", optional=True,
         target=("Erdrick's Cave", 28, 12), goal=("tile", 0x1D, 9, 3),
         lines=["North and a little west of Tantegel. There are no monsters inside.",
                "Inside: ITEM > Torch. Go down to the second floor; the chest holds the tablet.",
                "Story only. Safe to skip."]),
    dict(id="gear1", ch="1 · Setting out", title="Copper Sword, Leather Armor, Small Shield", rec=5,
         target=("Brecconary", 48, 41), goal=("map", 0x08),
         lines=["Earn gold nearby. Brecconary: Leather Armor 70 · Small Shield 90 · Copper Sword 180.",
                "Level 4: HURT (2 MP). Keep MP in reserve for HEAL."]),
    dict(id="garinham", ch="2 · The north", title="Find Garinham", rec=5,
         target=("Garinham", 2, 2), goal=("map", 0x09),
         lines=["Far to the northwest of Tantegel. Do not cross the western bridge.",
                "Talk to everyone. Inn: 25 G."]),
    dict(id="gear2", ch="2 · The north", title="Hand Axe, Chain Mail, Large Shield", rec=7,
         target=("Garinham", 2, 2), goal=("map", 0x09),
         lines=["Garinham: Chain Mail 300 · Hand Axe 560 · Large Shield 800.",
                "Chain Mail and Large Shield are otherwise only sold in the last town.",
                "Thrifty option: skip Chain Mail and save straight for Half Plate (1000)."]),
    dict(id="kol", ch="2 · The north", title="Travel to Kol", rec=7,
         target=("Kol", 104, 10), goal=("map", 0x07),
         lines=["Level 7: SLEEP. Very useful against Scorpions and Skeletons.",
                "Cross the bridge northeast of Tantegel, then a second bridge further east; Kol is north of it.",
                "Inn: 20 G."]),
    dict(id="flute", ch="2 · The north", title="Fairy Flute in Kol",
         target=("Kol", 104, 10), goal=("tile", 0x07, 9, 6),
         lines=["Stand exactly 4 tiles south of the bath and SEARCH.",
                "No key needed. You will use it later to put the Golem to sleep."]),
    dict(id="lv10", ch="2 · The north", title="Level 10 + Half Plate", rec=10,
         lines=["Level 9: RADIANT (light in caves). Level 10: STOPSPELL (against Warlocks).",
                "Half Plate 1000 G (Kol or Garinham). The Kol area is a good place to train."]),
    dict(id="swamp", ch="3 · Rimuldar", title="Swamp Cave: cross to the south", rec=10,
         target=("Swamp Cave (north entrance)", 104, 44), goal=("map", 0x15),
         lines=["South of Kol lies a poison swamp (hurts every step). Keep your HP up.",
                "Inside use a Torch or RADIANT and head for the south exit.",
                "The side branch has a Green Dragon guarding the princess. Avoid it for now."]),
    dict(id="rimuldar", ch="3 · Rimuldar", title="Run to Rimuldar", rec=10,
         target=("Rimuldar", 102, 72), goal=("map", 0x0B),
         lines=["Keep going south from the cave's south exit. Monsters are stronger here: just reach the town.",
                "Warlocks cast SLEEP: use STOPSPELL. Wolf, Wolflord: SLEEP."]),
    dict(id="keys", ch="3 · Rimuldar", title="Buy Magic Keys",
         target=("Rimuldar", 102, 72), goal=("map", 0x0B),
         lines=["Key shop: the NW hut, reachable only by walking around outside the moat. 53 G each, max 6.",
                "Buy six. Inn: 55 G. Rimuldar is your base from now on."]),
    dict(id="lv13", ch="3 · Rimuldar", title="Level 13, Broad Sword, Full Plate", rec=13,
         target=("Rimuldar", 102, 72),
         lines=["Train around Rimuldar; do not go far south (Wyvern, Wraith).",
                "Level 12: OUTSIDE (leave a cave). Level 13: RETURN (warp to Tantegel).",
                "Rimuldar: Broad Sword 1500 · Full Plate 3000 (or save for Magic Armor, 7700)."]),
    dict(id="stones", ch="4 · The three relics", title="Stones of Sunlight (Tantegel cellar)",
         target=("Tantegel", 43, 43), goal=("tile", 0x0C, 4, 5),
         lines=["RETURN to Tantegel. Open the locked door to the back area with a key.",
                "Walk down along the east side of the castle to the water, step one more tile right, "
                "go around the water to the stairs in the SE corner.",
                "The chest in the cellar holds the Stones of Sunlight."]),
    dict(id="harp", ch="4 · The three relics", title="Silver Harp (Garin's Grave)", rec=13,
         target=("Garinham", 2, 2), goal=("tile", 0x1A, 13, 6),
         lines=["Bring at least 2 keys. Garinham's large north building (key 1): inside, pass through "
                "the dark wall; the stairs behind the building lead down.",
                "B1: locked door in the bottom right (key 2), then the south corridor to the SW stairs.",
                "Follow the route line through B2, B3 and the tiny B4 up to the harp chest.",
                "Leave with OUTSIDE. Do not use the Cursed Belt."]),
    dict(id="staff", ch="4 · The three relics", title="Staff of Rain (Northern Shrine)",
         target=("Northern Shrine", 81, 1), goal=("tile", 0x0D, 3, 4),
         lines=["West of Kol at the north edge of the map. Reach it by walking NORTH of the mountain range.",
                "The old man trades the Silver Harp for the Staff of Rain."]),
    dict(id="lv15", ch="5 · The south", title="Level 15 + gold for Cantlin", rec=15,
         lines=["Good spots: south of Rimuldar, and the land below the Mountain Cave. Goldman = gold, Metal Slime = XP.",
                "Goal: Flame Sword 9800 + Silver Shield 14800 (24600 G in total). Level 15: REPEL.",
                "Do not linger past the western bridge (Wyvern, Knight, Wraith Knight) below level 15."]),
    dict(id="golem", ch="5 · The south", title="Cantlin: the Golem", rec=15,
         target=("Cantlin", 73, 102), goal=("tile", 0x01, 73, 100),
         lines=["Route: south from Garinham, west over the bridge below the Mountain Cave, south past the "
                "desert (Hauksness), then east.",
                "Run from monsters and heal often. A Golem attacks at the town gate:",
                "in battle use ITEM > Fairy Flute to put it to sleep, then FIGHT."]),
    dict(id="cantshop", ch="5 · The south", title="Cantlin: Flame Sword + Silver Shield",
         target=("Cantlin", 73, 102), goal=("map", 0x0A),
         lines=["Behind the locked NE door: Flame Sword 9800 · Silver Shield 14800, next to a key shop (98 G).",
                "Talk to everyone: here you learn Erdrick's Armor is buried under a tree in Hauksness.",
                "Inn: 100 G."]),
    dict(id="lv17", ch="5 · The south", title="Level 17 (HEALMORE)", rec=17,
         lines=["Without HEALMORE the Axe Knight and the Green Dragon are very risky.",
                "Train around Cantlin or Rimuldar."]),
    dict(id="armor", ch="5 · The south", title="Erdrick's Armor (Hauksness)", rec=17,
         target=("Hauksness", 25, 89), goal=("tile", 0x03, 18, 12),
         lines=["On the east side of the ruined town, step on the tree tile behind the swamp-covered shop: "
                "an Axe Knight attacks.",
                "STOPSPELL until it lands, then FIGHT + HEALMORE. You cannot run.",
                "Then SEARCH on that same tile. Do not step off it or you must fight again!",
                "The armor heals 1 HP per step, protects from swamp and barriers, and cuts fire/HURT damage by a third."]),
    dict(id="princess", ch="6 · The princess", title="Rescue Gwaelin", rec=17,
         target=("Swamp Cave", 104, 44), goal=("tile", 0x15, 4, 18),
         lines=["Bring 1 key. Swamp Cave side branch: Green Dragon (FIGHT + HEALMORE).",
                "Behind it a locked door. Talk to Gwaelin and carry her out."]),
    dict(id="return", ch="6 · The princess", title="Bring her back to the king",
         target=("Tantegel", 43, 43), goal=("tile", 0x05, 3, 4),
         lines=["OUTSIDE, then RETURN. Go up to the king in the throne room.",
                "Reward: Gwaelin's Love. It tells your distance from Tantegel and the XP to your next level."]),
    dict(id="token", ch="7 · The rainbow bridge", title="Erdrick's Token (swamp)",
         target=("Erdrick's Token", 83, 113), goal=("tile", 0x01, 83, 113),
         lines=["Exactly 70 south and 40 east of Tantegel, in the big swamp southeast of Cantlin.",
                "SEARCH on that exact tile. The map and the route line take you there."]),
    dict(id="drop", ch="7 · The rainbow bridge", title="Rainbow Drop (Southern Shrine)",
         target=("Southern Shrine", 108, 109), goal=("map", 0x0E),
         lines=["South of Rimuldar at the SE tip of the island; go around the south end of the mountains.",
                "Needs Erdrick's Token + Stones of Sunlight + Staff of Rain. You get the Rainbow Drop."]),
    dict(id="bridge", ch="7 · The rainbow bridge", title="Rainbow Bridge to Charlock",
         target=("tip of the peninsula", 65, 49), goal=("tile", 0x01, 65, 49),
         lines=["North of Rimuldar to the shore, then west along it to the tip of the peninsula, "
                "where a single tile of water separates you from the island.",
                "There: ITEM > Rainbow Drop. The bridge appears."]),
    dict(id="lv19", ch="8 · Charlock", title="Level 19-20", rec=19,
         lines=["Level 19: HURTMORE. Level 20+ is recommended for the Dragonlord.",
                "Good spots: Charlock island (Rimuldar is close) or the Cantlin area."]),
    dict(id="passage", ch="8 · Charlock", title="Charlock: the hidden stairs", rec=19,
         target=("Charlock Castle", 48, 48), goal=("tile", 0x02, 10, 1),
         lines=["The two visible staircases are false paths.",
                "Stand BEHIND the throne and SEARCH. A hidden staircase appears under you."]),
    dict(id="sword", ch="8 · Charlock", title="Erdrick's Sword", rec=19,
         target=("Charlock Castle", 48, 48), goal=("tile", 0x10, 5, 5),
         lines=["Go down to B4, then take the staircase that leads back UP: B3, B2, B1, and down again "
                "into the closed middle room of B2.",
                "The route line shows every staircase. Afterwards OUTSIDE + RETURN: save and refill."]),
    dict(id="dlord", ch="8 · Charlock", title="The Dragonlord", rec=20,
         target=("Charlock Castle", 48, 48), goal=("tile", 0x06, 17, 24),
         lines=["Before you go: save, full HP/MP, a few Herbs. Erdrick's Sword + Armor + Silver Shield.",
                "Answer NO to his offer! First form: weak.",
                "True form (dragon): only FIGHT and HEALMORE. SLEEP, STOPSPELL and HURT almost never work on him. "
                "Heal as soon as your HP drops below about 50."]),
    dict(id="ending", ch="8 · Charlock", title="Back to Tantegel: the end",
         target=("Tantegel", 43, 43), goal=("tile", 0x05, 3, 4),
         lines=["You hold the Ball of Light. Return to Tantegel Castle and talk to the king.", "Congratulations!"]),
]


# --------------------------------------------------------------------------
# GAME STATE FROM MEMORY
# --------------------------------------------------------------------------
class Game:
    """State decoded from NES RAM 0x000-0x10F plus (optionally) cartridge RAM 0x6000-0x602F."""

    def __init__(self, ram, sram=None):
        r = ram
        self.x, self.y, self.map = r[0x3A], r[0x3B], r[0x45]
        self.exp = r[0xBA] | (r[0xBB] << 8)
        self.gold = r[0xBC] | (r[0xBD] << 8)
        eq = r[0xBE]
        self.weapon, self.armor, self.shield = eq >> 5, (eq >> 2) & 7, eq & 3
        self.keys, self.herbs = r[0xBF], r[0xC0]
        self.items = set()
        for b in r[0xC1:0xC5]:
            self.items.add(b & 0x0F)
            self.items.add(b >> 4)
        self.items.discard(0)
        self.items.discard(15)
        self.hp, self.mp, self.level = r[0xC5], r[0xC6], r[0xC7]
        self.str, self.agi = r[0xC8], r[0xC9]
        self.maxhp, self.maxmp = r[0xCA], r[0xCB]
        self.atk, self.dfn = r[0xCC], r[0xCD]
        self.mods, self.pflags, self.story = r[0xCF], r[0xDF], r[0xE4]
        bits = r[0xCE] | ((self.mods & 3) << 8)
        self.spells = [SPELL_ORDER[i] for i in range(10) if bits & (1 << i)]
        self.radiant, self.repel = r[0xDA], r[0xDB]
        self.en_id, self.en_hp = r[0xE0], r[0xE2]
        self.en_stats = list(r[0x100:0x108]) if len(r) >= 0x108 else None
        # The killing blow takes the enemy's HP byte below zero and it wraps around (245 is -11).
        # No enemy ever has more than its base HP, so a larger number is a beaten enemy.
        if self.en_hp > (self.en_stats[2] if self.en_stats and self.en_stats[2] else 200):
            self.en_hp = 0
        self.valid = (1 <= self.level <= 30) and (1 <= self.map <= 0x1D) and self.maxhp > 0
        # Which adventure this is: the first four letters of the hero's name (DispName0-3,
        # 0xB5-0xB8) plus, when cartridge RAM is readable, the save file number (0x6039).
        self.hero = bytes(r[0xB5:0xB9]).hex()
        if sram and len(sram) >= 0x3A:
            self.hero += "-%d" % sram[0x39]
        self.opened = set()
        self.chr = None
        if sram and len(sram) >= 0x2C:
            self.chr = sram[3]
            for i in range(0x1C, 0x2C, 2):
                if sram[i] or sram[i + 1]:
                    self.opened.add((sram[i], sram[i + 1]))
        self.in_battle = self._battle()

    def _battle(self):
        if not self.valid or self.en_id >= len(ENEMIES):
            return False
        match = DATA is not None and self.en_stats == DATA["en"][self.en_id]
        if self.chr is not None:
            return self.chr == 3 and (match or DATA is None)
        return match and self.en_hp > 0

    def flags(self):
        f = {}
        f["left_throne"] = bool(self.pflags & 0x08) or self.map not in (0x05,)
        f["bridge"] = bool(self.mods & 0x08)
        f["drop"] = 14 in self.items or f["bridge"]
        f["staff"] = 13 in self.items or f["drop"]
        f["harp"] = 10 in self.items or f["staff"]
        f["stones"] = 12 in self.items or f["drop"]
        f["token"] = 7 in self.items or f["drop"]
        f["golem"] = bool(self.story & 0x02)
        f["flute"] = 5 in self.items or f["golem"]
        f["returned"] = bool(self.pflags & 0x02)
        f["princess"] = bool(self.pflags & 0x03)
        f["passage"] = bool(self.mods & 0x04)
        f["dl_dead"] = bool(self.story & 0x04)
        f["scale"] = bool(self.mods & 0x10)
        f["gdragon"] = bool(self.story & 0x40)      # the Swamp Cave's Green Dragon (set at CPU $E967)
        f["carrying"] = bool(self.pflags & 0x01)
        return f


# When is a step "done": g = Game, f = flags, v = set of maps/events seen so far
DONE = {
    "throne":   lambda g, f, v: f["left_throne"],
    "brecc":    lambda g, f, v: g.weapon >= 2 and g.armor >= 1,
    "lv3":      lambda g, f, v: g.level >= 3,
    "tablet":   lambda g, f, v: 0x1D in v or g.level >= 7,
    "gear1":    lambda g, f, v: g.weapon >= 3 and g.armor >= 2 and g.shield >= 1,
    "garinham": lambda g, f, v: 0x09 in v,
    "gear2":    lambda g, f, v: g.weapon >= 4 and g.armor >= 3 and g.shield >= 2,
    "kol":      lambda g, f, v: 0x07 in v,
    "flute":    lambda g, f, v: f["flute"],
    "lv10":     lambda g, f, v: g.level >= 10 and g.armor >= 4,
    "swamp":    lambda g, f, v: 0x15 in v or 0x0B in v,
    "rimuldar": lambda g, f, v: 0x0B in v,
    "keys":     lambda g, f, v: "keys" in v,
    "lv13":     lambda g, f, v: g.level >= 13 and g.weapon >= 5 and g.armor >= 5,
    "stones":   lambda g, f, v: f["stones"],
    "harp":     lambda g, f, v: f["harp"],
    "staff":    lambda g, f, v: f["staff"],
    "lv15":     lambda g, f, v: g.level >= 15,
    "golem":    lambda g, f, v: f["golem"],
    "cantshop": lambda g, f, v: g.weapon >= 6 and g.shield >= 3,
    "lv17":     lambda g, f, v: g.level >= 17,
    "armor":    lambda g, f, v: g.armor == 7,
    "princess": lambda g, f, v: f["princess"],
    "return":   lambda g, f, v: f["returned"],
    "token":    lambda g, f, v: f["token"],
    "drop":     lambda g, f, v: f["drop"],
    "bridge":   lambda g, f, v: f["bridge"],
    "lv19":     lambda g, f, v: g.level >= 19,
    "passage":  lambda g, f, v: f["passage"] or g.weapon == 7 or f["dl_dead"],
    "sword":    lambda g, f, v: g.weapon == 7,
    "dlord":    lambda g, f, v: f["dl_dead"],
    "ending":   lambda g, f, v: False,
}
SOFT = ("cantshop", "garinham", "kol", "swamp", "rimuldar", "keys")

# --------------------------------------------------------------------------
# ACHIEVEMENTS
# --------------------------------------------------------------------------
# Every condition rests on something read from the game itself:
#   - story flag 0x40 / 0x02 / 0x04 are set when the Swamp Cave's Green Dragon, the Golem and
#     the Dragonlord's true form fall (CPU $E95C-$E9E6); player flag 0x01 = carrying the princess
#   - a won battle adds exactly the enemy's table XP to the hero's XP, so a kill is "XP rose
#     by the XP of the enemy whose stats sit at 0x100"; the Dragonlord gives 0 XP (flag instead)
#   - 37 enemy types appear in the random encounter groups; the Golem is the 38th
#   - the level table at $F34B has 30 entries; the last one is 65,535 XP
#   - at 0 HP the hero is dead; the death routine ($EDBB) halves the gold and clears the
#     "carrying the princess" flag; keys and herbs stop at 6 (CMP #6 at $D7FB / $D6E7)
# "An adventure followed from its first step" = the companion saw the brand-new game in the
# throne room, so it knows nobody died along the way. The game keeps no such record itself
# (the disassembly's RAM map has no death counter). Adventures are told apart by the hero's
# name and the save file number, so the three save files do not mix.
# The two tuning numbers are choices, not game facts: 10 hours is the fast end of what players
# report for a full run (roughly 10 to 25 hours depending on the source), and level 19 is one
# below the level the walkthrough recommends for the Dragonlord.
BESTIARY = list(range(38))   # all but the Dragonlord's two forms: the 37 of the encounter groups + the Golem (tested)
ACH_TOWNS = (0x08, 0x09, 0x07, 0x0B, 0x0A, 0x03)
ALL_MAPS = tuple(range(0x01, 0x1E))
DRAGONS = (30, 34, 37)
MAX_LEVEL = 30
SPEED_LIMIT = 10 * 3600


def _kills(m, *ids):
    k = m.get("kills", {})
    return sum(k.get(str(i), 0) for i in ids)


def _types(m, f, ids):
    """How many of these enemy types have been defeated (flags count for the fixed fights)."""
    n = sum(1 for i in ids if _kills(m, i))
    if 24 in ids and not _kills(m, 24) and f["golem"]:
        n += 1
    if 30 in ids and not _kills(m, 30) and f["gdragon"]:
        n += 1
    return n


def _ev(m, name):
    return bool(m.get("ev", {}).get(name))


def _clean_run(m, g):
    run = m.get("runs", {}).get(g.hero)
    return run is not None and run.get("deaths", 1) == 0


def A(id, group, points, title, text, test, secret=False):
    return dict(id=id, group=group, points=points, title=title, text=text, test=test, secret=secret)


ACHIEVEMENTS = [
    # -- the quest itself ---------------------------------------------------------------
    A("out", "The quest", 5, "A hero sets out", "Leave the throne room of Tantegel",
      lambda g, f, m: f["left_throne"]),
    A("flute", "The quest", 10, "Lullaby", "Find the Fairy Flute in Kol",
      lambda g, f, m: 5 in g.items),
    A("stones", "The quest", 10, "Sunlight in the cellar", "Take the Stones of Sunlight from under Tantegel",
      lambda g, f, m: f["stones"]),
    A("harp", "The quest", 10, "Garin's song", "Bring the Silver Harp up from Garin's Grave",
      lambda g, f, m: f["harp"]),
    A("staff", "The quest", 10, "A fair trade", "Trade the harp for the Staff of Rain",
      lambda g, f, m: f["staff"]),
    A("golem", "The quest", 15, "The gatekeeper falls", "Defeat the Golem at the gate of Cantlin",
      lambda g, f, m: f["golem"]),
    A("armor", "The quest", 20, "Under the tree", "Win Erdrick's Armor from the Axe Knight in Hauksness",
      lambda g, f, m: g.armor == 7),
    A("gdragon", "The quest", 15, "Dragon of the marsh", "Defeat the Green Dragon that guards the princess",
      lambda g, f, m: f["gdragon"] or f["princess"]),
    A("princess", "The quest", 15, "In your arms", "Carry Princess Gwaelin out of her cell",
      lambda g, f, m: f["princess"]),
    A("return", "The quest", 10, "Gwaelin's Love", "Bring the princess home to the king",
      lambda g, f, m: f["returned"]),
    A("token", "The quest", 15, "Proof of the bloodline", "Find Erdrick's Token in the southern swamp",
      lambda g, f, m: f["token"]),
    A("drop", "The quest", 20, "Rain and sunlight", "Receive the Rainbow Drop",
      lambda g, f, m: f["drop"]),
    A("bridge", "The quest", 10, "The rainbow bridge", "Raise the bridge to Charlock",
      lambda g, f, m: f["bridge"]),
    A("passage", "The quest", 10, "Behind the throne", "Uncover the hidden stairs in Charlock Castle",
      lambda g, f, m: f["passage"] or g.weapon == 7 or f["dl_dead"]),
    A("sword", "The quest", 20, "Erdrick's Sword", "Take Erdrick's Sword from the depths of Charlock",
      lambda g, f, m: g.weapon == 7),
    A("dlord", "The quest", 50, "Light restored", "Defeat the Dragonlord's true form",
      lambda g, f, m: f["dl_dead"]),
    # -- the hero ------------------------------------------------------------------------
    A("lv10", "The hero", 10, "Apprentice", "Reach level 10",
      lambda g, f, m: (g.level, 10)),
    A("lv20", "The hero", 20, "Champion", "Reach level 20",
      lambda g, f, m: (g.level, 20)),
    A("lv30", "The hero", 50, "Legend of Alefgard", "Reach level 30, the last one: 65,535 experience",
      lambda g, f, m: (g.level, MAX_LEVEL)),
    A("spells", "The hero", 10, "Full spellbook", "Learn all ten spells",
      lambda g, f, m: (len(g.spells), 10)),
    A("kit", "The hero", 20, "Erdrick's heir", "Wear Erdrick's Sword and Erdrick's Armor with the Silver Shield",
      lambda g, f, m: g.weapon == 7 and g.armor == 7 and g.shield == 3),
    A("keys", "The hero", 5, "Jangling pockets", "Carry six Magic Keys, as many as the hero can hold",
      lambda g, f, m: (g.keys, 6)),
    A("gold10k", "The hero", 10, "Nest egg", "Carry 10,000 gold",
      lambda g, f, m: (g.gold, 10000)),
    A("gold50k", "The hero", 30, "King's ransom", "Carry 50,000 gold",
      lambda g, f, m: (g.gold, 50000)),
    # -- battle --------------------------------------------------------------------------
    A("win1", "Battle", 5, "First blood", "Win a battle",
      lambda g, f, m: m.get("wins", 0) >= 1),
    A("win100", "Battle", 10, "Seasoned", "Win 100 battles",
      lambda g, f, m: (m.get("wins", 0), 100)),
    A("win500", "Battle", 25, "Veteran of Alefgard", "Win 500 battles",
      lambda g, f, m: (m.get("wins", 0), 500)),
    A("slimes", "Battle", 10, "Slime season", "Defeat 50 Slimes or Red Slimes",
      lambda g, f, m: (_kills(m, 0, 1), 50)),
    A("metal1", "Battle", 15, "Quicksilver", "Defeat a Metal Slime before it runs",
      lambda g, f, m: _kills(m, 16) >= 1),
    A("metal10", "Battle", 30, "Metal fatigue", "Defeat 10 Metal Slimes",
      lambda g, f, m: (_kills(m, 16), 10)),
    A("goldmen", "Battle", 10, "Gold rush", "Defeat 10 Goldmen",
      lambda g, f, m: (_kills(m, 25), 10)),
    A("dragons", "Battle", 25, "Dragon hunter", "Defeat a Green Dragon, a Blue Dragon and a Red Dragon",
      lambda g, f, m: (_types(m, f, DRAGONS), 3)),
    A("bestiary", "Battle", 50, "Monster manual",
      "Defeat every kind of monster that roams Alefgard: all %d, the Golem included" % len(BESTIARY),
      lambda g, f, m: (_types(m, f, BESTIARY), len(BESTIARY))),
    A("thread", "Battle", 15, "By a thread", "Win a battle with 3 HP or less left",
      lambda g, f, m: _ev(m, "thread")),
    # -- the land ------------------------------------------------------------------------
    A("towns", "The land", 10, "Grand tour", "Visit Brecconary, Garinham, Kol, Rimuldar, Cantlin and Hauksness",
      lambda g, f, m: (sum(1 for t in ACH_TOWNS if t in m.get("maps", ())), len(ACH_TOWNS))),
    A("tablet", "The land", 5, "Erdrick's words", "Reach the tablet chamber at the bottom of Erdrick's Cave",
      lambda g, f, m: 0x1D in m.get("maps", ())),
    A("maps", "The land", 25, "Cartographer", "Set foot on all %d maps, from the overworld to the bottom of Charlock" % len(ALL_MAPS),
      lambda g, f, m: (sum(1 for t in ALL_MAPS if t in m.get("maps", ())), len(ALL_MAPS))),
    A("ring", "The land", 5, "Fighter's Ring", "Find the Fighter's Ring in the Mountain Cave",
      lambda g, f, m: 6 in g.items or bool(g.mods & 0x20)),
    A("necklace", "The land", 15, "Bad luck charm", "Find the Death Necklace",
      lambda g, f, m: 11 in g.items),
    # -- challenges ----------------------------------------------------------------------
    A("clean10", "Challenge", 20, "Careful steps",
      "Reach level 10 without dying, in an adventure followed from its first step",
      lambda g, f, m: _clean_run(m, g) and g.level >= 10),
    A("noflute", "Challenge", 25, "No lullaby", "Defeat the Golem without the Fairy Flute in your pack",
      lambda g, f, m: _ev(m, "golem_noflute")),
    A("dl19", "Challenge", 40, "Ahead of schedule", "Defeat the Dragonlord at level 19 or lower",
      lambda g, f, m: 0 < m.get("ev", {}).get("dl_level", 0) <= 19),
    A("nosword", "Challenge", 40, "Borrowed steel", "Defeat the Dragonlord without Erdrick's Sword in hand",
      lambda g, f, m: _ev(m, "dl_nosword")),
    A("duty", "Challenge", 30, "Duty first", "Defeat the Dragonlord while the princess is still in her cell",
      lambda g, f, m: _ev(m, "dl_noprincess")),
    A("fast", "Challenge", 30, "Before supper",
      "Defeat the Dragonlord within 10 hours of play, in an adventure followed from its first step",
      lambda g, f, m: 0 < m.get("ev", {}).get("dl_time", 0) <= SPEED_LIMIT),
    A("clean", "Challenge", 50, "Unbroken",
      "Defeat the Dragonlord without dying once, in an adventure followed from its first step",
      lambda g, f, m: _ev(m, "dl_clean")),
    # -- hidden until found ----------------------------------------------------------------
    A("dead", "Hidden", 5, "Thou art dead", "Fall in battle. Half of your gold stays behind",
      lambda g, f, m: m.get("deaths", 0) >= 1, secret=True),
    A("cursed", "Hidden", 5, "Curiosity", "Put on a cursed item",
      lambda g, f, m: bool(g.mods & 0xC0), secret=True),
    A("dropped", "Hidden", 10, "Back to the cell", "Die with the princess in your arms. She is returned to her cell",
      lambda g, f, m: _ev(m, "dropped"), secret=True),
    A("carry", "Hidden", 30, "Two against the dark", "Defeat the Dragonlord with the princess in your arms",
      lambda g, f, m: _ev(m, "dl_carry"), secret=True),
]

TOWNS = {0x03, 0x04, 0x05, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E}
TARGET_MAP = {"Brecconary": 0x08, "Garinham": 0x09, "Kol": 0x07, "Rimuldar": 0x0B, "Cantlin": 0x0A,
              "Hauksness": 0x03, "Tantegel": 0x04, "Northern Shrine": 0x0D, "Southern Shrine": 0x0E}


def compass(dx, dy):
    """dx>0 = east, dy>0 = south (game coordinates)."""
    if dx == 0 and dy == 0:
        return "YOU ARE HERE"
    parts = []
    if dy:
        parts.append("%d %s" % (abs(dy), "south" if dy > 0 else "north"))
    if dx:
        parts.append("%d %s" % (abs(dx), "east" if dx > 0 else "west"))
    return " · ".join(parts)



# --------------------------------------------------------------------------
# WORLD MODEL: tiles, walkability, routes
# --------------------------------------------------------------------------
W_WALK = set("01267b")          # overworld: grass, desert, hills, forest, swamp, bridge
W_PORTAL = set("89ac")          # town, cave, castle, stairs
T_WALK = set("0135678 9abe".replace(" ", ""))   # towns: grass sand chest stairs brick trees swamp barrier door bridge
D_WALK = set("12345")           # dungeons: stairs, brick, chest, door


class World:
    def __init__(self, data):
        self.d = data
        self.rows = {1: data["world"]}
        self.size = {1: (120, 120)}
        self.dun = {1: False}
        for k, m in data["maps"].items():
            k = int(k)
            self.rows[k] = m["rows"]
            self.size[k] = (m["w"], m["h"])
            # From the game's tile-set choice (CPU $B020): dungeon tiles only from map 0x0F up.
            # The cellar and the shrines (0x0C-0x0E) are stored 3 bits per tile like dungeons
            # but are drawn and walked with the town tile set.
            self.dun[k] = bool(m["dun"])
        self.links = {}
        self.entry = {}   # town map -> overworld tile it sits on
        for sm, sx, sy, tm, tx, ty in data["links"]:
            self.links.setdefault((sm, sx, sy), []).append((tm, tx, ty))
            self.links.setdefault((tm, tx, ty), []).append((sm, sx, sy))
            if sm == 1:
                self.entry[tm] = (1, sx, sy)
        self.chests = {}
        for m, x, y, t in data["chests"]:
            self.chests.setdefault(m, []).append((x, y, CHEST.get(t, "?")))

    def tile(self, m, x, y):
        w, h = self.size[m]
        if 0 <= x < w and 0 <= y < h:
            return self.rows[m][y][x]
        return None

    def enemies_at(self, g):
        return self.enemies(g.map, g.x, g.y)

    def enemies(self, m, x=0, y=0):
        """The enemy types of the random encounters on a map (on the overworld: around a tile)."""
        d = self.d
        if m == 1:
            row = d["grid"][min(7, y // 15)][min(7, x // 15)]
        elif m == 0x02:
            row = 0x10
        elif m == 0x03:
            row = 0x0D
        elif m == 0x06:
            row = 0x12
        elif 0x0F <= m <= 0x1B:
            row = d["cave"][m - 0x0F]
        else:
            return []
        out = []
        for e in d["groups"][row]:
            if e not in out:
                out.append(e)
        return out

    def step_cost(self, m, x, y, g, goal):
        """Cost of stepping ONTO a tile, or None if it cannot be walked on."""
        t = self.tile(m, x, y)
        if t is None:
            return None
        armor = g.armor == 7
        if m == 1:
            if (x, y) == (64, 49) and g.mods & 0x08:
                return 1
            if t in W_PORTAL:
                return 60
            if t not in W_WALK:
                return None
            if t == "7":
                return 1 if armor else 4
            return 2 if t == "2" else 1
        if self.dun[m]:
            if t == "6":
                return 1 if goal == ("tile", m, x, y) else None
            if t not in D_WALK:
                return None
            if t == "5":
                return 25 if g.keys else 400
            return 1
        if t not in T_WALK:
            return None
        if t == "b":
            return 25 if g.keys else 400
        if t == "a":
            return 1 if armor else 12
        if t == "9":
            return 1 if armor else 4
        return 1

    def route(self, g, goal, limit=60000):
        """Dijkstra from the player's tile to the goal. Returns list of (map, x, y) or None."""
        start = (g.map, g.x, g.y)
        passage = bool(g.mods & 0x04)

        def is_goal(n):
            return n[0] == goal[1] if goal[0] == "map" else n == goal[1:]

        dist = {start: 0}
        prev = {}
        pq = [(0, start)]
        seen = 0
        while pq:
            c, n = heapq.heappop(pq)
            if c > dist.get(n, 1e9):
                continue
            if is_goal(n):
                path = [n]
                while n in prev:
                    n = prev[n]
                    path.append(n)
                return path[::-1]
            seen += 1
            if seen > limit:
                break
            m, x, y = n
            nxt = []
            for l in self.links.get(n, ()):
                if n == (0x02, 10, 1) and not passage:
                    continue
                nxt.append((l, 1))
            w, h = self.size[m]
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    sc = self.step_cost(m, nx, ny, g, goal)
                    if sc is not None:
                        nxt.append(((m, nx, ny), sc))
                elif m in self.entry and 1 < m < 0x0C:
                    nxt.append((self.entry[m], 1))      # walk off the edge of a town
            for nn, sc in nxt:
                nc = c + sc
                if nc < dist.get(nn, 1e9):
                    dist[nn] = nc
                    prev[nn] = n
                    heapq.heappush(pq, (nc, nn))
        return None

    def describe_route(self, path):
        """One-line summary: total steps and the next waypoint."""
        if not path or len(path) < 2:
            return "You are on the spot."
        steps = len(path) - 1
        doors = sum(1 for (m, x, y) in path[1:] if m != 1 and self.tile(m, x, y) == ("5" if self.dun[m] else "b"))
        m0 = path[0][0]
        nxt = ""
        for i in range(1, len(path)):
            if path[i][0] != m0:
                a, b = path[i - 1], path[i]
                if m0 == 1:
                    nxt = "enter %s at %s" % (MAPS[b[0]], rel_tant(a[1], a[2]))
                elif (a in self.links) and b in self.links[a]:
                    kind = "stairs"
                    nxt = "%s at (%d,%d) to %s, %d steps away" % (kind, a[1], a[2], MAPS[b[0]], i - 1)
                else:
                    nxt = "walk off the map edge to the overworld, %d steps away" % (i - 1)
                break
        s = "Route: %d steps" % steps
        if nxt:
            s += " · next: " + nxt
        if doors:
            s += " · %d locked door%s on the way" % (doors, "" if doors == 1 else "s")
        return s


def rel_tant(x, y):
    r = compass(x - TANTEGEL[0], y - TANTEGEL[1])
    return "Tantegel" if r == "YOU ARE HERE" else r + " of Tantegel"


def describe(step, g):
    """Straight-line compass line for the step's world target."""
    tgt = step.get("target")
    if not tgt:
        return ""
    if g is not None and g.valid:
        if (tgt[1], tgt[2]) == TANTEGEL:
            return "" if g.map in (0x04, 0x05, 0x0C) else "Tantegel: cast RETURN (level 13+) or use Wings"
        if g.map == 0x01:
            return "%s: %s" % (tgt[0], compass(tgt[1] - g.x, tgt[2] - g.y))
        if g.map in TOWNS and TARGET_MAP.get(tgt[0]) != g.map:
            return "%s is %s" % (tgt[0], rel_tant(tgt[1], tgt[2]))
        return ""
    return "%s is %s" % (tgt[0], rel_tant(tgt[1], tgt[2]))


def stats_line(g):
    s = "Lv %d   HP %d/%d   MP %d/%d   G %d" % (g.level, g.hp, g.maxhp, g.mp, g.maxmp, g.gold)
    if g.level < len(XP_TABLE):
        s += "   next lv: %d XP" % max(0, XP_TABLE[g.level] - g.exp)
    return s


def gear_line(g):
    s = "ATK %d · DEF %d   |   %s · %s · %s" % (g.atk, g.dfn, WEAPONS[g.weapon], ARMORS[g.armor], SHIELDS[g.shield])
    return s


def self_lines(g):
    """The 'my stats' panel."""
    cost = DATA["cost"] if DATA else [4, 2, 2, 3, 2, 6, 8, 2, 10, 5]
    out = ["STR %d · AGI %d · XP %d · keys %d · herbs %d" % (g.str, g.agi, g.exp, g.keys, g.herbs)]
    if g.spells:
        sp = ["%s %d" % (n, cost[SPELL_ORDER.index(n)]) for n in g.spells]
        line = "Spells (MP): " + " · ".join(sp)
        heal = "HEALMORE" if "HEALMORE" in g.spells else ("HEAL" if "HEAL" in g.spells else None)
        if heal:
            line += "   [%s x%d left]" % (heal, g.mp // cost[SPELL_ORDER.index(heal)])
        out.append(line)
    nxt = [lv for lv in sorted(SPELLS) if lv > g.level]
    extra = []
    if nxt:
        extra.append("next spell: %s at Lv %d" % (SPELLS[nxt[0]], nxt[0]))
    if g.repel:
        extra.append("REPEL active")
    if g.mods & 0x10:
        extra.append("wearing Dragon's Scale")
    if g.mods & 0x20:
        extra.append("wearing Fighter's Ring")
    if g.mods & 0xC0:
        extra.append("CURSED")
    if extra:
        out.append(" · ".join(extra))
    inv = [ITEMS[i] for i in sorted(g.items) if i in ITEMS]
    if inv:
        out.append("Items: " + ", ".join(inv))
    return out


# -- battle math (formulas from the game's own routines) ----------------------
def hero_damage(atk, en_def):
    a = atk - en_def // 2
    return (0, 1) if a < 2 else (a // 4, (2 * a) // 4)


def enemy_damage(en_atk, hero_def):
    a = en_atk - hero_def // 2
    thr = en_atk // 2 + 1
    if a >= thr:
        return (a // 4, (2 * a) // 4)
    return (0, (thr + 1) // 3)


def enemy_spells(b):
    out = []
    hi, lo = b >> 4, b & 15
    pct = (0, 25, 50, 75)
    if hi & 3:
        out.append("%s %d%%" % (("SLEEP", "STOPSPELL", "HEAL", "HEALMORE")[hi >> 2], pct[hi & 3]))
    if lo & 3:
        out.append("%s %d%%" % (("HURT", "HURTMORE", "fire breath", "strong fire breath")[lo >> 2], pct[lo & 3]))
    return out


def battle_lines(g, max_seen):
    """Lines for the battle panel. max_seen = highest enemy HP seen in this fight."""
    att, dfn, base_hp, spell, agi, mdef, exp, gold = g.en_stats
    lo, hi = hero_damage(g.atk, dfn)
    elo, ehi = enemy_damage(att, g.dfn)
    lines = ["ATK %d · DEF %d · base HP %d · reward %d XP, %d G" % (att, dfn, base_hp, exp, gold)]
    sp = enemy_spells(spell)
    lines.append("Uses: " + (", ".join(sp) if sp else "physical attacks only"))
    ok = lambda r: "%d%%" % round(100 * (16 - r) / 16)
    lines.append("Your spell odds: SLEEP %s · STOPSPELL %s · HURT/HURTMORE %s · dodges %d/64"
                 % (ok(agi >> 4), ok(agi & 15), ok(mdef >> 4), mdef & 15))
    avg = (lo + hi) / 2.0
    hits = "" if avg <= 0 or g.en_hp <= 0 else "  (about %d more hit%s)" % (
        max(1, int(-(-g.en_hp // avg))), "" if g.en_hp <= avg else "s")
    lines.append("Your hit: %d-%d%s   ·   its hit: %d-%d" % (lo, hi, hits, elo, ehi))
    st = []
    if g.pflags & 0x40:
        st.append("enemy ASLEEP")
    if g.pflags & 0x20:
        st.append("enemy spells BLOCKED")
    if g.pflags & 0x80:
        st.append("YOU are asleep")
    if g.pflags & 0x10:
        st.append("YOUR spells are blocked")
    if st:
        lines.append(" · ".join(st))
    return lines



COL_WORLD = {"0": "#3f9142", "1": "#d8c37c", "2": "#86a14e", "3": "#7b6a58", "4": "#2b5ea6", "5": "#4a4a52",
             "6": "#1f6a2c", "7": "#7a4f9a", "8": "#ffd24a", "9": "#111111", "a": "#ffffff", "b": "#c08a45",
             "c": "#111111"}
COL_TOWN = {"0": "#3f9142", "1": "#d8c37c", "2": "#2b5ea6", "3": "#f2c14e", "4": "#55565e", "5": "#f4f4ff",
            "6": "#a89c8a", "7": "#9fc4ff", "8": "#1f6a2c", "9": "#7a4f9a", "a": "#e04fd0", "b": "#8a4b1e",
            "c": "#ff8c3a", "d": "#ff8c3a", "e": "#c08a45", "f": "#6b2f2f"}
COL_DUN = {"0": "#20222b", "1": "#f4f4ff", "2": "#8d8272", "3": "#9fc4ff", "4": "#f2c14e", "5": "#8a4b1e",
           "6": "#ff9ad5", "7": "#000000"}


# --------------------------------------------------------------------------
# THE FULL-SIZE MAP: places, what is there, and what is still to do
# --------------------------------------------------------------------------
# A place is one name for the maps that belong together. kind: the filter it is listed under.
PLACES = [
    ("Tantegel Castle", (0x04, 0x05, 0x0C), "town"), ("Brecconary", (0x08,), "town"),
    ("Garinham", (0x09,), "town"), ("Kol", (0x07,), "town"), ("Rimuldar", (0x0B,), "town"),
    ("Cantlin", (0x0A,), "town"), ("Hauksness", (0x03,), "town"),
    ("Northern Shrine", (0x0D,), "town"), ("Southern Shrine", (0x0E,), "town"),
    ("Erdrick's Cave", (0x1C, 0x1D), "cave"), ("Swamp Cave", (0x15,), "cave"),
    ("Mountain Cave", (0x16, 0x17), "cave"), ("Garin's Grave", (0x18, 0x19, 0x1A, 0x1B), "cave"),
    ("Charlock Castle", (0x02, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x06), "cave"),
]
PLACE_OF = {m: i for i, (_, maps, _) in enumerate(PLACES) for m in maps}
INSIDE = {"Garin's Grave": "Garinham"}       # a place entered through another one, not from the overworld
ATLAS_FILTERS = [("town", "Towns, castles, shrines"), ("cave", "Caves and dungeons"), ("quest", "Quest spots"),
                 ("chest", "Chests"), ("stairs", "Stairs and exits"), ("zone", "Monster zones"),
                 ("route", "Route"), ("names", "Names")]
ATLAS_LEGEND = [("now", "The current step is here"), ("todo", "Still something to do"),
                ("later", "Needed later in the walkthrough"), ("done", "Done, nothing left here"),
                ("optional", "Optional, never needed")]
STATUS_RANK = {"now": 0, "todo": 1, "later": 2, "done": 3, "optional": 4, "info": 5}


def step_place(step):
    """Index into PLACES of the place a step happens in, "world" for a tile of the overworld, else None."""
    goal = step.get("goal")
    if not goal:
        return None
    if goal[1] == 0x01:
        return "world" if goal[0] == "tile" else None
    return PLACE_OF.get(goal[1])


# --------------------------------------------------------------------------
# PLUGIN
# --------------------------------------------------------------------------
for _s in STEPS:
    _soft = _s.get("optional") or _s["id"].startswith(("gear", "lv")) or _s["id"] in SOFT
    _s["soft"] = bool(_soft)
    _s["anchor"] = not (_s.get("optional") or _s["id"].startswith(("gear", "lv")))


class DragonWarrior(GamePlugin):
    id = "dragon_warrior"
    title = "Dragon Warrior"
    system = "NES"
    year = 1989
    publisher = "Enix / Nintendo"
    blurb = ("The first Dragon Quest. Rescue Princess Gwaelin, gather Erdrick's relics, cross the "
             "Rainbow Bridge and defeat the Dragonlord.")
    accent = "#f2c14e"
    cores = ("mesen", "fceumm", "nestopia")
    rom_exts = (".nes",)
    # 3b3f88f0 is the owner's "Dragon Warrior (USA).nes" as a whole file (iNES header included);
    # its tables give FINGERPRINT. The other two are other dumps/revisions, not re-checked.
    crc32 = ("caaf5c6b", "d4d5f5d7", "3b3f88f0")
    name_pattern = r"^dragon warrior(?![\s_\-]*(ii|iii|iv|vii|[2-9]|monsters|i\s*&))"
    memory = ((0x0000, 0x110, True), (0x6000, 0x40, False))
    moby_id = 9223        # MobyGames id of "Dragon Warrior" (NES, 1986), checked through their API
    steps = STEPS

    def __init__(self):
        d = load_data()
        self.world = World(d) if d else None
        self._route = (None, None)
        self._fight = None
        self._run = None

    # -- the game's tables, from the player's own copy ----------------------------
    def data_status(self):
        if self.world is not None:
            return ""
        return ("Choose your Dragon Warrior (USA) ROM once: the map, routes, monster lists and battle "
                "details are read from it. Nothing from the game comes with Retro Companion")

    def prepare(self, path):
        global DATA
        try:
            with open(path, "rb") as fh:
                d = extract(fh.read(0x20000))
        except (OSError, ValueError, IndexError) as exc:
            return "Could not read that file (%s)" % exc
        if hashlib.sha256(_canonical(d).encode("utf-8")).hexdigest() != FINGERPRINT:
            return ("That file is not Dragon Warrior (USA), first release (PRG0). Other versions "
                    "keep their tables elsewhere and are not supported yet")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(d, fh, separators=(",", ":"))
            os.replace(DATA_FILE + ".tmp", DATA_FILE)
        except OSError as exc:
            return "Could not save the game's tables (%s)" % exc
        DATA = d
        self.world = World(d)
        self._route = (None, None)
        return ""

    def parse(self, blocks):
        g = Game(blocks[0], blocks[1] if len(blocks) > 1 else None)
        return g if g.valid else None

    def is_fresh_start(self, g):
        return g.map == 0x05 and g.exp == 0 and not (g.pflags & 0x08)

    def observe(self, g, seen):
        seen.add(g.map)
        if g.keys > 0 and 0x0B in seen:
            seen.add("keys")

    def step_done(self, step, g, seen):
        return bool(DONE[step["id"]](g, g.flags(), seen))

    def summary(self, g):
        return "Lv %d · %s" % (g.level, MAPS.get(g.map, "?"))

    # -- achievements ------------------------------------------------------------
    achievements = ACHIEVEMENTS

    def track(self, g, prev, m, dt):
        runs = m.setdefault("runs", {})                # one record per adventure (hero name + save file)
        if self.is_fresh_start(g):                     # a brand-new game: start following it
            runs[g.hero] = {"deaths": 0, "time": 0.0}
        run = runs.get(g.hero)
        if run is not None:
            run["time"] = run.get("time", 0.0) + dt
        self._run = run
        maps = m.setdefault("maps", [])
        if g.map not in maps:
            maps.append(g.map)
        # Everything below is about a change between two states of the same play. Loading a
        # save always puts the hero in the throne room, so "same map" rules a load out.
        if prev is None or prev.map != g.map:
            return
        ev = m.setdefault("ev", {})
        if prev.hp > 0 and g.hp == 0:
            m["deaths"] = m.get("deaths", 0) + 1
            if run is not None:
                run["deaths"] = run.get("deaths", 0) + 1
            if prev.pflags & 0x01:
                ev["dropped"] = 1
        # A won battle: the game adds EnBaseExp (0x106, the XP byte of the enemy stats it copied
        # to 0x100 when the fight began) to the hero's XP. So "XP rose by exactly that byte"
        # is the win, and EnNumber (0xE0) says whose.
        gain = g.exp - prev.exp
        foe = prev.en_id
        if prev.en_stats and gain > 0 and gain == prev.en_stats[6] and foe < len(ENEMIES):
            kills = m.setdefault("kills", {})
            kills[str(foe)] = kills.get(str(foe), 0) + 1
            m["wins"] = m.get("wins", 0) + 1
            if 0 < g.hp <= 3:
                ev["thread"] = 1
        f, pf = g.flags(), prev.flags()
        if f["golem"] and not pf["golem"] and 5 not in g.items and 5 not in prev.items:
            ev["golem_noflute"] = 1
        if f["dl_dead"] and not pf["dl_dead"]:
            ev["dl_level"] = min(g.level, ev.get("dl_level") or g.level)
            if g.pflags & 0x01:
                ev["dl_carry"] = 1
            if not g.pflags & 0x03:
                ev["dl_noprincess"] = 1
            if g.weapon != 7:
                ev["dl_nosword"] = 1
            if run is not None:
                ev["dl_time"] = min(run["time"], ev.get("dl_time") or run["time"])
                if run.get("deaths", 1) == 0:
                    ev["dl_clean"] = 1

    def achieved(self, ach, g, m):
        return ach["test"](g, g.flags(), m)

    def events(self, g, prev):
        """What just happened, for the overlay's log. Only changes inside one play count:
        another hero (a loaded save file) or a brand-new game says nothing."""
        if prev is None or prev.hero != g.hero or self.is_fresh_start(g):
            return []
        out = []
        if prev.map != g.map:
            return ["Entered %s" % MAPS.get(g.map, "an unknown place")]
        gain = g.exp - prev.exp
        if prev.en_stats and gain > 0 and gain == prev.en_stats[6] and prev.en_id < len(ENEMIES):
            won = g.gold - prev.gold
            out.append("Defeated %s · +%d XP%s" % (ENEMIES[prev.en_id], gain, ", +%d G" % won if won > 0 else ""))
        if prev.hp > 0 and g.hp == 0:
            out.append("Fell in battle. Half of the gold is lost")
        if g.level > prev.level:
            spell = SPELLS.get(g.level)
            out.append("Reached level %d%s" % (g.level, ". Learned %s" % spell if spell else ""))
        new = sorted(g.items - prev.items)
        if 0 < len(new) <= 2:
            out += ["Got %s" % ITEMS[i] for i in new if i in ITEMS]
        for name, table, now, was in (("weapon", WEAPONS, g.weapon, prev.weapon), ("armor", ARMORS, g.armor, prev.armor),
                                      ("shield", SHIELDS, g.shield, prev.shield)):
            if now != was and now:
                out.append("Equipped %s" % table[now])
        return out

    def run_line(self):
        """One line for the stats module: is this adventure being followed, and how is it going."""
        run = self._run
        if run is None:
            return "Adventure not followed from its start: the no-death and timed challenges are off"
        t = int(run.get("time", 0))
        d = run.get("deaths", 0)
        return "Adventure followed from its start · %s · %d h %02d min" % (
            "no deaths" if d == 0 else ("1 death" if d == 1 else "%d deaths" % d), t // 3600, (t % 3600) // 60)

    def banner(self):
        return dict(rows=DATA["world"], palette=COL_WORLD, y0=30, h=30) if DATA else None

    # -- helpers -----------------------------------------------------------------
    def route_for(self, g, goal):
        key = (g.map, g.x, g.y, goal, g.keys > 0, g.armor == 7, g.mods & 0x0C)
        if self._route[0] != key:
            self._route = (key, self.world.route(g, goal))
        return self._route[1]

    def map_spec(self, g, path, goal, zoomed):
        W = self.world
        w, h = W.size[g.map]
        if g.map == 1 and zoomed:
            span = 38
            x0 = max(0, min(w - span, g.x - span // 2))
            y0 = max(0, min(h - span, g.y - span // 2))
            vw = vh = span
            z = 380 // span
        else:
            x0 = y0 = 0
            vw, vh = w, h
            z = 3 if g.map == 1 else max(2, min(380 // w, 330 // h, 14))
        rects, labels = [], []
        if g.map == 1 and g.mods & 0x08:
            rects.append((64, 49, "#ff7bd0"))
        if g.map == 0x02 and g.mods & 0x04:
            rects.append((10, 1, "#9fc4ff"))
        for i, (x, y, name) in enumerate(W.chests.get(g.map, ()), 1):
            if (x, y) in g.opened:
                rects.append((x, y, "#5a5142"))
            elif z >= 9:
                labels.append((x, y, str(i)))
        on_map = [(x, y) for (m, x, y) in (path or ()) if m == g.map]
        mark = None
        if goal and goal[0] == "tile" and goal[1] == g.map:
            mark = (goal[2], goal[3])
        elif on_map:
            mark = on_map[-1]
        pal = COL_WORLD if g.map == 1 else (COL_DUN if W.dun[g.map] else COL_TOWN)
        return dict(base=g.map, rows=W.rows[g.map], palette=pal, x0=x0, y0=y0, vw=vw, vh=vh, z=z,
                    rects=rects, labels=labels, path=on_map, goal=mark, player=(g.x, g.y))

    # -- the full-size map -------------------------------------------------------
    def atlas(self, g, ctx):
        W = self.world
        if W is None:
            return None
        steps, done, seen = self.steps, ctx.done, ctx.seen
        cur = ctx.current
        # "now" is the step the player is on; a training step has no place, so the next one that has
        now = next((i for i in range(cur, len(steps)) if steps[i]["id"] not in done and step_place(steps[i]) is not None),
                   None)

        def state(i):
            if steps[i]["id"] in done:
                return "done"
            return "now" if i == now else ("todo" if i < cur else "later")

        def summed(idx, visited):
            """One status for a place from the steps that happen there."""
            if not idx:
                return "optional"
            st = min((state(i) for i in idx), key=STATUS_RANK.get)
            if st == "done" and not visited and all(steps[i].get("optional") for i in idx):
                return "optional"
            return st

        def step_lines(idx):
            word = {"done": "done", "now": "the current step", "todo": "still open", "later": "later"}
            return ["Step %d: %s (%s)" % (i + 1, steps[i]["title"], word[state(i)]) for i in idx]

        by_place = {}
        for i, s in enumerate(steps):
            by_place.setdefault(step_place(s), []).append(i)
        names = [n for n, _, _ in PLACES]
        info = []                       # per place: status, the lines of its mark
        for pi, (name, maps, kind) in enumerate(PLACES):
            idx = list(by_place.get(pi, []))
            for child, parent in INSIDE.items():
                if parent == name:
                    idx += by_place.get(names.index(child), [])
            visited = any(m in seen for m in maps)
            st = summed(sorted(idx), visited)
            lines = step_lines(sorted(idx)) or ["No step of the walkthrough leads here. Treasure only"]
            lines.append("You have been here" if visited else "Not visited yet")
            loot = [c for m in maps for (_, _, c) in W.chests.get(m, ())]
            if loot:
                lines.append("Chests: " + ", ".join(loot))
            en = []
            for m in maps:
                en += [e for e in W.enemies(m) if e not in en]
            if en:
                lines.append("Monsters: " + ", ".join(ENEMIES[e] for e in en))
            lines += LOC.get(maps[0], [])[:2]
            info.append((st, lines))

        path = {}
        goal = ctx.step.get("goal")
        if g is not None and goal:
            for m, x, y in self.route_for(g, goal) or ():
                path.setdefault(m, []).append((x, y))
        out = {"here": g.map if g is not None else None, "player": (g.x, g.y) if g is not None else None,
               "filters": ATLAS_FILTERS, "legend": ATLAS_LEGEND, "order": [1], "maps": {}}

        def add(marks, x, y, kind, name, status, lines, goto=None, label=False):
            for mk in marks:            # two things on one tile: one mark carrying both
                if (mk["x"], mk["y"]) == (x, y) and mk["kind"] == kind:
                    mk["lines"] = mk["lines"] + [name] + list(lines)
                    if STATUS_RANK[status] < STATUS_RANK[mk["status"]]:
                        mk["status"] = status
                    return
            marks.append(dict(x=x, y=y, kind=kind, name=name, status=status, lines=list(lines), goto=goto, label=label))

        # the overworld
        marks = []
        doors = {}
        for sm, sx, sy, tm, tx, ty in W.d["links"]:
            if sm == 1 and tm in PLACE_OF:
                doors.setdefault(PLACE_OF[tm], []).append((sy, sx, tm))
        for pi, lst in doors.items():
            name, maps, kind = PLACES[pi]
            lst.sort()
            for k, (sy, sx, tm) in enumerate(lst):
                tag = "" if len(lst) == 1 else (" (north entrance)" if k == 0 else " (south entrance)")
                add(marks, sx, sy, kind, name + tag, info[pi][0], info[pi][1], goto=tm, label=True)
        for i in by_place.get("world", []):
            _, _, x, y = steps[i]["goal"]
            add(marks, x, y, "quest", steps[i]["title"], state(i),
                step_lines([i]) + steps[i]["lines"] + ["%s" % rel_tant(x, y)], label=True)
        areas = []
        for zy in range(8):
            for zx in range(8):
                en = W.enemies(1, zx * 15, zy * 15)
                areas.append((zx * 15, zy * 15, zx * 15 + 14, zy * 15 + 14,
                              ["Monsters around here: " + ", ".join(
                                  "%s (HP %d, ATK %d)" % (ENEMIES[e], DATA["en"][e][2], DATA["en"][e][0]) for e in en)
                               if en else "No monsters around here"]))
        rects = [(64, 49, "#ff7bd0")] if g is not None and g.mods & 0x08 else []
        left = sorted(i for i in range(len(steps)) if steps[i]["id"] not in done)
        out["maps"][1] = dict(
            name=MAPS[1], status=state(now) if now is not None else "done", rows=W.rows[1], palette=COL_WORLD,
            notes=(["Next: step %d, %s" % (now + 1, steps[now]["title"])] if now is not None else [])
            + ["%d of %d steps done" % (len(steps) - len(left), len(steps)),
               "Click a place for what is there and whether you still have something to do in it. "
               "A double click opens its own map. Click anywhere else for the monsters of that area"],
            marks=marks, areas=areas, path=path.get(1, []), rects=rects)

        # every other map
        for pi, (name, maps, kind) in enumerate(PLACES):
            for m in maps:
                marks = []
                for i in by_place.get(pi, []):
                    gl = steps[i]["goal"]
                    if gl[0] == "tile" and gl[1] == m:
                        add(marks, gl[2], gl[3], "quest", steps[i]["title"], state(i),
                            step_lines([i]) + steps[i]["lines"], label=True)
                for k, (x, y, what) in enumerate(W.chests.get(m, ()), 1):
                    opened = g is not None and g.map == m and (x, y) in g.opened
                    add(marks, x, y, "chest", "%d %s" % (k, what), "info",
                        ["Chest: %s" % what] + (["Opened"] if opened else []))
                for a, b in W.links.items():
                    if a[0] != m:
                        continue
                    for tm, tx, ty in b:
                        add(marks, a[1], a[2], "stairs", "To %s" % MAPS[tm], "info",
                            ["Leads to %s" % MAPS[tm]], goto=tm)
                rects = []
                if g is not None and g.map == m:
                    rects = [(x, y, "#5a5142") for (x, y, _) in W.chests.get(m, ()) if (x, y) in g.opened]
                if m == 0x02 and g is not None and g.mods & 0x04:
                    rects.append((10, 1, "#9fc4ff"))
                en = W.enemies(m)
                notes = step_lines(sorted(i for i in by_place.get(pi, [])
                                          if steps[i]["goal"][1] == m or len(maps) == 1))
                notes.append("You have been here" if m in seen else "Not visited yet")
                if en:
                    notes.append("Monsters: " + ", ".join(
                        "%s (HP %d, ATK %d)" % (ENEMIES[e], DATA["en"][e][2], DATA["en"][e][0]) for e in en))
                notes += LOC.get(m, [])
                out["order"].append(m)
                out["maps"][m] = dict(name=MAPS[m], status=info[pi][0], rows=W.rows[m],
                                      palette=COL_DUN if W.dun[m] else COL_TOWN, notes=notes, marks=marks,
                                      areas=[], path=path.get(m, []), rects=rects)
        return out

    # -- the overlay content -----------------------------------------------------
    def view(self, g, ctx):
        step = ctx.step
        goal = step.get("goal")
        if g is None:
            return {"nav": [describe(step, None)], "tips": item_tips(None)}
        v = {"tips": item_tips(g)}
        loc = MAPS.get(g.map, "?")
        v["location"] = loc + ("  (%s)" % rel_tant(g.x, g.y) if g.map == 0x01 else "  (%d,%d)" % (g.x, g.y))
        v["stats"], v["gear"], v["self"] = stats_line(g), gear_line(g), self_lines(g) + [self.run_line()]
        v["short"] = {"stats": "Lv %d  HP %d/%d  MP %d/%d  G %d" % (g.level, g.hp, g.maxhp, g.mp, g.maxmp, g.gold)}
        if g.in_battle:
            if not self._fight or self._fight[0] != g.en_id or g.en_hp > self._fight[1]:
                self._fight = (g.en_id, g.en_hp)
            mx = max(1, self._fight[1])
            hp = "HP %d / %d" % (g.en_hp, mx) if g.en_hp > 0 else "defeated"
            v["battle"] = {"title": "%s   %s" % (ENEMIES[g.en_id].upper(), hp),
                           "frac": g.en_hp / float(mx), "lines": battle_lines(g, mx)}
            if g.en_stats:
                v["battle"]["short"] = "you hit %d-%d · it hits %d-%d" % (
                    hero_damage(g.atk, g.en_stats[1]) + enemy_damage(g.en_stats[0], g.dfn))
        else:
            self._fight = None
        W = self.world
        path = self.route_for(g, goal) if goal and W else None
        nav = [describe(step, g)]
        if goal and W:
            nav.append(self.world.describe_route(path) if path else
                       "No walkable route found from here (a key, the Rainbow Bridge or the hidden "
                       "stairs may be missing).")
        v["nav"] = nav
        if goal and W and path:                 # the compact guide: the route's length, or the compass line
            v["short"]["nav"] = nav[-1].split(" · ")[0]
        elif nav[0]:
            v["short"]["nav"] = nav[0]
        warn = []
        rec = step.get("rec")
        if rec and g.level < rec:
            warn.append("Recommended level: %d (you are %d)" % (rec, g.level))
        if g.hp <= max(8, g.maxhp * 0.3):
            warn.append("LOW HP: heal!")
        if 9 in g.items or 11 in g.items:
            warn.append("You carry a cursed item. Do not use it; sell it.")
        if W is None:
            warn.append("Map and routes are off: choose your Dragon Warrior ROM in the library")
        v["warn"] = warn
        notes = []
        en = W.enemies_at(g) if W else ()
        if en:
            notes.append("Monsters here: " + ", ".join(
                "%s (HP %d, ATK %d)" % (ENEMIES[e], DATA["en"][e][2], DATA["en"][e][0]) for e in en))
        ch = W.chests.get(g.map) if W else None
        if ch:
            notes.append("Chests: " + " · ".join("%d %s%s" % (i, n, " (opened)" if (x, y) in g.opened else "")
                                                 for i, (x, y, n) in enumerate(ch, 1)))
        notes.extend(LOC.get(g.map, []))
        v["notes"] = notes
        if W:
            v["map"] = self.map_spec(g, path, goal, ctx.zoom)
        return v


PLUGIN = DragonWarrior()
