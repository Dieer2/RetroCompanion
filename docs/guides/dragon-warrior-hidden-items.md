title: Where the hidden items are in Dragon Warrior
description: The exact tiles for the Fairy Flute, Erdrick's Armor, Erdrick's Token and the hidden stairs in Charlock, read from the game's own code.
date: 2026-11-13

Dragon Warrior hides five things in places where nothing shows on screen. You have to stand on one exact tile and use SEARCH, or use an item on one exact tile. The townspeople give hints, but the hints are vague. The places below were read from the part of the game's code that checks where you are standing, so they are exact.

Coordinates are given as (x, y) on the map you are on, counted from the top left corner and starting at zero. On the overworld the game counts distances from Tantegel Castle, which sits at (43, 43).

| Item | Map | Tile | What to do there |
| --- | --- | --- | --- |
| Fairy Flute | Kol | (9, 6) | SEARCH |
| Erdrick's Armor | Hauksness | (18, 12) | Win the fight, then SEARCH |
| Erdrick's Token | Overworld | (83, 113) | SEARCH |
| Rainbow Bridge | Overworld | (65, 49) | Use the Rainbow Drop |
| Hidden stairs | Charlock Castle | (10, 1) | SEARCH |

::figure world

## Fairy Flute

The flute is in Kol, four tiles south of the bath. Stand there and use SEARCH. You need no key and no fight.

You use it once. A Golem guards the gate of Cantlin, and in that fight the flute, picked from the item menu, puts it to sleep. A man behind a locked door in the Rimuldar inn tells you where the flute is, but you can skip him.

## Erdrick's Armor

The armor is in Hauksness, the ruined town in the southwest desert. The tile is a tree on the east side, behind the old shop that is covered in swamp. People in Cantlin tell you the armor is buried under a tree, and this is the tree.

Stepping on it starts a fight with an Axe Knight, and you cannot run. After you win, do not move. Use SEARCH on the same tile. If you step off and back on, you fight him again.

Come at level 17 or higher. The Axe Knight casts SLEEP, so cast STOPSPELL until it works, then attack and heal with HEALMORE.

The armor is worth the trouble. It heals one hit point on every step. Swamp and barrier tiles no longer hurt you; without it they cost 2 and 15 hit points a step. An enemy's HURT, HURTMORE and fire breath do two thirds of their damage, and an enemy's STOPSPELL never works on you.

## Erdrick's Token

The token lies in the big swamp southeast of Cantlin. From Tantegel that is 70 tiles south and 40 tiles east. Stand on the tile and use SEARCH.

A sage in the south part of Cantlin gives you these two numbers. He sits behind locked doors and barrier tiles that cost 15 hit points a step, so he is easy to miss.

Gwaelin's Love makes the search easy. It reports how far north or south and east or west of the castle you are. Walk until it says 70 to the south and 40 to the east.

::tool love

You need the token for the old man in the Southern Shrine. He wants it together with the Stones of Sunlight and the Staff of Rain before he hands over the Rainbow Drop.

## The Rainbow Bridge

The Rainbow Drop works on one tile only, the tip of the peninsula northwest of Rimuldar. One tile of water lies between it and the island of Charlock. Pick the drop from the item menu while you stand there and the bridge appears. Anywhere else nothing happens.

## The hidden stairs in Charlock

On the ground floor of Charlock Castle you can see two staircases, behind locked doors and barriers. Both lead nowhere. The real way down is under the tile behind the throne. Stand there and use SEARCH, and a staircase opens under you.

## Two more that are easy to miss

The Stones of Sunlight are not hidden by a search, but the way to them is. In Tantegel Castle, open the locked door to the back area, walk down the east side to the water, step one tile to the right, and go around the water to a staircase in the southeast corner. The chest is in the cellar.

Erdrick's Sword is in a closed room on the second basement floor of Charlock. No door leads into it from that floor. You have to go down to the fourth floor and take the staircase that leads back up.

## Sources

The five tiles come from the game's own check routines in Dragon Warrior (USA). What each item does, and what the townspeople say, comes from the game's text and from play. [Retro Companion](/) marks these tiles on its live map when the walkthrough reaches them.
