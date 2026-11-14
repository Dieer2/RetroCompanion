title: Dragon Warrior level chart: experience for all 30 levels and every spell
description: The full experience table of Dragon Warrior on the NES, the level at which each of the ten spells is learned, their magic cost, and what level to reach before each part of the game.
date: 2026-11-13

Dragon Warrior has 30 levels and ten spells. The table below is the game's own level table, read from the cartridge. The numbers are the total experience you need to reach each level.

::tool xp

::figure xp

## Experience table

| Level | Total experience | From the level before | Spell learned |
| --- | --- | --- | --- |
| 1 | 0 | | |
| 2 | 7 | 7 | |
| 3 | 23 | 16 | HEAL |
| 4 | 47 | 24 | HURT |
| 5 | 110 | 63 | |
| 6 | 220 | 110 | |
| 7 | 450 | 230 | SLEEP |
| 8 | 800 | 350 | |
| 9 | 1,300 | 500 | RADIANT |
| 10 | 2,000 | 700 | STOPSPELL |
| 11 | 2,900 | 900 | |
| 12 | 4,000 | 1,100 | OUTSIDE |
| 13 | 5,500 | 1,500 | RETURN |
| 14 | 7,500 | 2,000 | |
| 15 | 10,000 | 2,500 | REPEL |
| 16 | 13,000 | 3,000 | |
| 17 | 16,000 | 3,000 | HEALMORE |
| 18 | 19,000 | 3,000 | |
| 19 | 22,000 | 3,000 | HURTMORE |
| 20 | 26,000 | 4,000 | |
| 21 | 30,000 | 4,000 | |
| 22 | 34,000 | 4,000 | |
| 23 | 38,000 | 4,000 | |
| 24 | 42,000 | 4,000 | |
| 25 | 46,000 | 4,000 | |
| 26 | 50,000 | 4,000 | |
| 27 | 54,000 | 4,000 | |
| 28 | 58,000 | 4,000 | |
| 29 | 62,000 | 4,000 | |
| 30 | 65,535 | 3,535 | |

Level 30 costs 65,535 because the game keeps your experience in two bytes of memory, and 65,535 is the largest number two bytes can hold. The counter stops there.

## The ten spells

| Spell | Level | Magic cost | What it does |
| --- | --- | --- | --- |
| HEAL | 3 | 4 | Restores 10 to 17 hit points |
| HURT | 4 | 2 | Does 5 to 12 damage |
| SLEEP | 7 | 2 | Puts the enemy to sleep |
| RADIANT | 9 | 3 | Lights 7 by 7 tiles in a cave |
| STOPSPELL | 10 | 2 | Stops the enemy from casting |
| OUTSIDE | 12 | 6 | Takes you out of a cave |
| RETURN | 13 | 8 | Takes you to Tantegel Castle |
| REPEL | 15 | 2 | Keeps weak monsters away for 127 steps |
| HEALMORE | 17 | 10 | Restores 85 to 100 hit points |
| HURTMORE | 19 | 5 | Does 58 to 65 damage |

The numbers are the ones in the game's code. Each healing or attack spell is a fixed number plus a small roll: HEAL is 10 plus a roll from 0 to 7. RADIANT does not stay at full size. After 80 steps the lit area shrinks to 5 by 5 tiles, 60 steps later to 3 by 3, and after 60 more only your own tile is lit. Cast it again and it is back to 7 by 7.

Three of these change how you travel. RADIANT means you can stop buying Torches. OUTSIDE and RETURN together get you from the bottom of any cave back to the king in two casts, which costs 14 magic points. Keep that much in reserve when you go underground.

## What level for which part

These are the levels the Retro Companion walkthrough asks for. You can go earlier, but the fights get risky.

| Part of the game | Level |
| --- | --- |
| First fights around Tantegel | 1 to 3 |
| Walk to Garinham | 5 |
| Walk to Kol | 7 |
| Swamp Cave and the run to Rimuldar | 10 |
| Garin's Grave for the Silver Harp | 13 |
| Cantlin and the Golem | 15 |
| Axe Knight in Hauksness, Green Dragon in the Swamp Cave | 17 |
| Charlock Castle | 19 |
| The Dragonlord | 20 or more |

Level 17 matters most. HEALMORE is what keeps you alive against the Axe Knight, the Green Dragon and the Dragonlord's second form.

## Where experience comes from

A won fight adds exactly the experience listed for that enemy. There is no bonus and no random part. The Dragonlord is the exception: both of his forms give zero experience, so the last fight never raises your level.

Metal Slimes give the most experience for their strength, but they run away often. Goldmen give little experience and a lot of gold, which is what you need before Cantlin.

## Sources

The spell figures were read from the code of Dragon Warrior (USA). [What the game's code says](/guides/dragon-warrior-game-code-facts) gives the addresses.

The level table is at address $F34B in the code of Dragon Warrior (USA) and has 30 entries. The first twenty match the table published by Gamer Corner Guides. Spell levels and costs come from the game's data. [Retro Companion](/) shows the experience left to your next level and your next spell while you play.
