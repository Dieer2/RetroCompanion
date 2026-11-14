"""What is new, for players: one list, shown in the program (library window, "What's new")
and written to the website by tools/make_guides.py (site/news.html).

Only things a player can see or use belong here, newest first, each with its date. Server
upkeep and the admin page do not. `title` is a version of the program or a short name for
something on the website.
"""

NEWS = [
    dict(date="2026-11-14", title="Version 0.10", items=[
        "The figures in the item and spell tips are now read from the game's own code: Herb 23 to 30 HP, HEAL "
        "10 to 17, HEALMORE 85 to 100, HURT 5 to 12, HURTMORE 58 to 65, a Torch lights 3 by 3 tiles and "
        "RADIANT 7 by 7, REPEL and Fairy Water last 127 steps, swamp costs 2 HP a step and a barrier 15",
        "New in the tips: Erdrick's Armor also stops an enemy's STOPSPELL, Magic Armor does not weaken fire "
        "breath, and the Fighter's Ring does nothing at all",
        "The battle window tells how much damage the enemy's spell or fire breath does, in the armor you wear",
    ]),
    dict(date="2026-11-14", title="Version 0.9", items=[
        "Rest the pointer on a weapon, armor, shield, item or spell named anywhere in the overlay and a small "
        "window tells what it does: attack or defense, how it compares with what you wear, its price, whether "
        "you have the gold, where it is sold and what a shop pays for it. It works for what you carry and for "
        "what the shops of a town sell",
    ]),
    dict(date="2026-11-14", title="Version 0.8", items=[
        "The program updates itself. It looks for a new version when it starts, tells you at the bottom of "
        "the library when there is one, and \"Update and restart\" downloads it, checks it against the "
        "checksum of the release and starts the new version. Your settings and progress stay as they are. "
        "The check can be switched off in the settings",
    ]),
    dict(date="2026-11-14", title="Version 0.7", items=[
        "Ideas: suggest a feature and vote on the ideas of other players, in the program (Ideas, at the bottom "
        "of the library) and on the website. The list shows what is planned, what is open for votes and what "
        "is done. It needs a free account; one account has one vote on each idea",
    ]),
    dict(date="2026-11-14", title="Version 0.6", items=[
        "The shop has more to spend points on: three more achievement chimes (Coin, Bells, Harp; each can be "
        "heard before buying), two more pop-up styles (a slim banner, and a card edged in the grade's colour) "
        "and bronze, silver, gold and platinum frames for the profile picture",
        "An earned achievement can also show as a message inside RetroArch, which helps in exclusive "
        "fullscreen where the overlay cannot show. RetroArch can save a screenshot at that moment too. Both "
        "are in the settings",
        "Discord can show the game you are playing, your level and place, and the step you are on. It is off "
        "until you switch it on in the settings",
    ]),
    dict(date="2026-11-14", title="Version 0.5", items=[
        "Achievement pop-up: an earned achievement slides in at the top of the screen with the trophy of its "
        "grade and Retro Companion's own chime. The sound can be switched off in the overlay's right-click menu",
        "Earned achievements carry a trophy in the colour of their grade in the overlay's achievements window",
        "Full-size map (F, or the corner icon of the map window): the whole of Alefgard with place names. "
        "Drag it to move, turn the wheel to zoom, click a place to read what is there",
        "The map tells for every town, cave and shrine whether you are done there, still have something to do, "
        "will need it later in the walkthrough, or never need it at all",
        "Every town, cave and dungeon floor has its own map with the chests, what is in them, and where each "
        "staircase leads. Filters switch towns, caves, quest spots, chests, stairs, monster zones, the route "
        "and the names on and off",
        "Profile picture in the library: twenty built-in portraits, or your own PNG or GIF picture",
        "This list: what is new, in the program and on the website",
    ]),
    dict(date="2026-11-14", title="Version 0.4", items=[
        "Compact form for every overlay window: one strip with an icon and the main figures, so the game "
        "stays visible. C switches all of them (Ctrl+Shift+C in RetroArch)",
    ]),
    dict(date="2026-11-14", title="Version 0.3", items=[
        "A beaten enemy now reads 0 HP in the battle window instead of a full bar",
        "Achievements window in the overlay: every achievement of the game, one group at a time",
        "Event log window: enemies beaten, levels, items, finished steps and achievements, newest first",
    ]),
    dict(date="2026-11-14", title="Open source", items=[
        "Retro Companion is open source under the MIT license. The program is downloaded from its release "
        "page on GitHub, where it is built from the public source",
    ]),
    dict(date="2026-11-13", title="Guides", items=[
        "Six Dragon Warrior guides on the website: the 32-step walkthrough, hidden items, levels and spells, "
        "shop prices, facts read from the game's code, and the game's history",
        "Tools inside the guides: experience, damage and gold calculators, Gwaelin's Love, tickable steps",
    ]),
    dict(date="2026-11-13", title="Supporters", items=[
        "A supporter page on the website. Retro Companion stays free; supporters pay for the server and the "
        "time each new game takes",
    ]),
    dict(date="2026-11-12", title="Version 0.2", items=[
        "First public version: the game library, the live walkthrough overlay for Dragon Warrior with map, "
        "routes and battle details, 50 achievements, trophies and levels, accounts and the leaderboard",
    ]),
]
