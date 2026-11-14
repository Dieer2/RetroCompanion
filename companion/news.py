"""What is new, for players: one list, shown in the program (library window, "What's new")
and written to the website by tools/make_guides.py (site/news.html).

Only things a player can see or use belong here, newest first, each with its date. Server
upkeep and the admin page do not. `title` is a version of the program or a short name for
something on the website.
"""

NEWS = [
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
