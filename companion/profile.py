"""The player's profile across all games: trophies, level, and points to spend.

Every achievement of every game is also a trophy. Its grade follows from its points
(bronze under 15, silver 15 to 29, gold from 30), and unlocking all achievements of a game
adds that game's platinum trophy, worth PLATINUM_POINTS more.

    earned   all points ever earned, in every game. Decides the level; never goes down.
    spent    points paid in the shop.
    balance  earned - spent: what can still be spent.

The shop sells things that can only be had for points: other colour themes, extra overlay
modules, achievement chimes, pop-up styles and frames for the profile picture. Each item has a price and a level it needs. Nothing here costs money and
nothing in it is needed to play: the walkthrough, the map and the achievements stay free.

All of this lives in the local store file, so it is an honour system: there is no account
and no server to check it. Rankings between players would need both.
"""

PLATINUM_POINTS = 100
GRADES = ("bronze", "silver", "gold", "platinum")
TITLES = ((1, "Squire"), (2, "Wanderer"), (3, "Adventurer"), (4, "Knight"), (5, "Champion"),
          (7, "Hero"), (10, "Legend"))

SHOP = [
    dict(id="warm", kind="theme", title="Warm", price=0, level=1,
         text="The standard look: warm paper tones on a dark desk"),
    dict(id="graphite", kind="theme", title="Graphite", price=150, level=1,
         text="Colour theme: neutral greys, nothing warm about it"),
    dict(id="ink", kind="theme", title="Ink", price=150, level=2,
         text="Colour theme: cool blue-black, like a night sky"),
    dict(id="paper", kind="theme", title="Paper", price=300, level=3,
         text="Colour theme: light, dark ink on warm paper"),
    dict(id="tracker", kind="module", title="Trophy tracker", price=200, level=2,
         text="Overlay module: the three achievements you are closest to, with live progress"),
    # the sound of an earned achievement (companion/sound.py)
    dict(id="trophy", kind="chime", title="Fanfare", price=0, level=1,
         text="The standard chime: four rising notes that land on a ringing chord"),
    dict(id="coin", kind="chime", title="Coin", price=100, level=1,
         text="Two bright notes, short and quick"),
    dict(id="bells", kind="chime", title="Bells", price=150, level=2,
         text="Three soft bells going up a chord"),
    dict(id="harp", kind="chime", title="Harp", price=200, level=3,
         text="A harp run up two octaves"),
    # how the achievement pop-up looks (overlay.Popup)
    dict(id="card", kind="popup", title="Card", price=0, level=1,
         text="The standard pop-up: trophy, title, what it was for, points"),
    dict(id="banner", kind="popup", title="Banner", price=150, level=2,
         text="A slim strip: trophy, title and points on one line, so it covers less of the game"),
    dict(id="edge", kind="popup", title="Grade edge", price=250, level=3,
         text="The card with an edge and a filled trophy badge in the colour of the grade"),
    # a frame around the profile picture
    dict(id="plain", kind="frame", title="No frame", price=0, level=1, text="The picture as it is"),
    dict(id="bronze", kind="frame", title="Bronze frame", price=50, level=1, text="A bronze edge around your picture"),
    dict(id="silver", kind="frame", title="Silver frame", price=150, level=3, text="A silver edge around your picture"),
    dict(id="gold", kind="frame", title="Gold frame", price=300, level=5, text="A gold edge around your picture"),
    dict(id="platinum", kind="frame", title="Platinum frame", price=500, level=7,
         text="A platinum edge around your picture"),
]
# kinds where exactly one item is in use at a time, with the free item that is the default
ONE_OF = {"theme": "warm", "chime": "trophy", "popup": "card", "frame": "plain"}
KINDS = (("theme", "Colour themes"), ("module", "Overlay modules"), ("chime", "Achievement chimes"),
         ("popup", "Achievement pop-ups"), ("frame", "Picture frames"))


def grade(points):
    return "gold" if points >= 30 else ("silver" if points >= 15 else "bronze")


def level_floor(level):
    """Points needed to be at this level: 0, 100, 300, 600, 1000, 1500, ..."""
    return 50 * level * (level - 1)


class Profile:
    def __init__(self, data, achievements, save):
        """data: the store's profile dict; achievements: {game id: Achievements}."""
        self.d = data
        self.d.pop("spent", None)               # older stores kept this; it is derived now
        self.d.setdefault("owned", [])
        self.d.setdefault("use", {})
        self.ach = achievements
        self._save = save

    # -- trophies and points -------------------------------------------------------
    def platinum(self, gid):
        a = self.ach[gid]
        return bool(a.items) and a.count() == len(a.items)

    def trophies(self):
        t = dict.fromkeys(GRADES, 0)
        for gid, a in self.ach.items():
            for x in a.items:
                if x["id"] in a.unlocked:
                    t[grade(x["points"])] += 1
            if self.platinum(gid):
                t["platinum"] += 1
        return t

    def earned(self):
        return sum(a.points() + (PLATINUM_POINTS if self.platinum(gid) else 0) for gid, a in self.ach.items())

    def spent(self):
        """What the owned items cost. Derived, so two computers can never disagree about it."""
        return sum(i["price"] for i in SHOP if i["id"] in self.d["owned"])

    def balance(self):
        return self.earned() - self.spent()

    def level(self):
        e, n = self.earned(), 1
        while level_floor(n + 1) <= e:
            n += 1
        return n

    def title(self):
        lv = self.level()
        return [t for need, t in TITLES if need <= lv][-1]

    def level_progress(self):
        """(points into this level, points this level spans)."""
        lv = self.level()
        return self.earned() - level_floor(lv), level_floor(lv + 1) - level_floor(lv)

    # -- shop ------------------------------------------------------------------------
    def owns(self, item_id):
        item = next(i for i in SHOP if i["id"] == item_id)
        return item["price"] == 0 or item_id in self.d["owned"]

    def in_use(self, item):
        if item["kind"] in ONE_OF:
            return self.choice(item["kind"]) == item["id"]
        return bool(self.d["use"].get(item["id"]))

    def choice(self, kind):
        """The item in use of a kind where one is chosen (theme, chime, popup, frame)."""
        t = self.d["use"].get(kind, ONE_OF[kind])
        return t if any(i["id"] == t and i["kind"] == kind for i in SHOP) and self.owns(t) else ONE_OF[kind]

    def theme(self):
        return self.choice("theme")

    def modules(self):
        """Extra overlay modules that are owned and switched on."""
        return {i["id"] for i in SHOP if i["kind"] == "module" and self.owns(i["id"]) and self.d["use"].get(i["id"])}

    def why_not(self, item):
        """'' if the item can be bought now, else the reason."""
        if self.owns(item["id"]):
            return "owned"
        if self.level() < item["level"]:
            return "Needs level %d" % item["level"]
        if self.balance() < item["price"]:
            return "%d more points needed" % (item["price"] - self.balance())
        return ""

    def buy(self, item):
        if self.why_not(item):
            return False
        self.d["owned"].append(item["id"])
        self.use(item, True)
        return True

    def use(self, item, on=True):
        if not self.owns(item["id"]):
            return
        if item["kind"] in ONE_OF:
            self.d["use"][item["kind"]] = item["id"]
        else:
            self.d["use"][item["id"]] = bool(on)
        self._save()
