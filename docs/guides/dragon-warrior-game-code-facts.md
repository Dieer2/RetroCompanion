title: Twelve things the code of Dragon Warrior says about how the game works
description: What happens when you die, why level 30 stops at 65,535, how damage is worked out, what every spell and item does in numbers, and other rules of Dragon Warrior read from the game's own code.
date: 2026-11-13

Retro Companion follows a game by reading its memory. To build that for Dragon Warrior, the game's code had to be read first. Some of what it says settles old questions that guides answer in different ways. Everything below is from Dragon Warrior (USA) on the NES. Addresses are given for readers who want to check them.

## 1. Dying costs half your gold, and the princess

The routine that runs when your hit points reach zero is at $EDBB. It does two things to your save. It halves your gold. It also clears the flag that says you are carrying Princess Gwaelin, so if you die on the way back to the castle with her, you are no longer carrying her. Your experience, items and equipment are left alone.

This is why spending gold before a hard fight is always right. What you turned into a sword cannot be halved.

## 2. Level 30 is a limit of the memory

Your experience is kept in two bytes, at addresses $BA and $BB. Two bytes can hold numbers up to 65,535. The level table at $F34B has 30 entries, and the last one is exactly 65,535. The designers set the top level at the largest number the counter can hold.

## 3. A won fight gives exactly the listed experience

When a battle starts, the game copies the enemy's stats to address $0100. One of those bytes is the experience it is worth. When you win, that number is added to your total with nothing added or taken away.

The overlay uses this to count kills. If your experience rises by exactly the amount stored for the current enemy, that enemy was beaten.

## 4. The Dragonlord is worth nothing

Both forms of the Dragonlord have zero in the experience and gold fields. The game marks his defeat with a story flag instead. Three of these flags matter for the story: one for the Green Dragon that guards the princess, one for the Golem at Cantlin and one for the Dragonlord's true form. They are set between $E95C and $E9E6.

## 5. There are 40 enemies, and 37 of them roam

The enemy table has 40 entries. Thirty-seven appear in the random encounter groups. The Golem is the 38th and is met only once, at the gate of Cantlin. Outside the 37 it is the only enemy that gives experience, and it gives little: 5. The last two entries are the two forms of the Dragonlord.

The Green Dragon and the Axe Knight you meet at fixed places are ordinary entries from the 37. The Axe Knight in Hauksness comes back if you step off his tile and on again.

## 6. Keys and Herbs stop at six

The code compares your count with six before it adds a Magic Key or an Herb. The checks are at $D7FB and $D6E7. There is no way to carry a seventh.

## 7. Hidden items are plain coordinate checks

When you use SEARCH, the game compares the map you are on and your position with a short list. Kol at (9, 6) gives the Fairy Flute. Hauksness at (18, 12) gives Erdrick's Armor. The world map at (83, 113) gives Erdrick's Token. In Charlock, (10, 1) opens the hidden stairs. The Rainbow Drop works the same way: it does something only at (65, 49) on the world map.

Nothing about these tiles is stored in the map itself. That is why they look like any other tile.

## 8. How damage is worked out

Your attack power minus half of the enemy's defense gives a base number. A hit does between a quarter and a half of that base. If the base is below two, the hit does zero or one.

Enemy hits use the same idea with your defense, but with a floor. If your defense is high enough to push the base under about half of the enemy's attack power, the game stops using the base and rolls a small number instead. So no amount of armor brings an enemy's hits down to nothing.

For example, with attack power 40 against a Skeleton, whose defense is 22, the base is 40 minus 11, which is 29. Your hits do 7 to 14.

::tool damage

## 9. Spells and Herbs are a fixed number plus a small roll

HEAL takes a random number from 0 to 7 and adds 10. That is the whole spell, at $DBB8. The others are built the same way.

| What | Lowest | Highest |
| --- | --- | --- |
| Herb | 23 | 30 |
| HEAL | 10 | 17 |
| HEALMORE | 85 | 100 |
| HURT | 5 | 12 |
| HURTMORE | 58 | 65 |
| An enemy's HURT | 3 | 10 |
| An enemy's HURTMORE | 30 | 45 |
| An enemy's HEAL | 20 | 27 |
| An enemy's HEALMORE | 85 | 100 |
| Fire breath | 16 | 23 |
| Strong fire breath | 65 | 72 |

An Herb restores more than HEAL does, 23 at worst against 17 at best. The enemy versions of HURT and HURTMORE are weaker than yours. The enemy's HEAL is stronger than yours, and its HEALMORE is the same.

## 10. Light and REPEL count your steps

A Torch sets the lit area to 3 by 3 tiles, at $DD47, and it stays that way until you leave the cave. RADIANT raises it to 7 by 7 and starts a counter of 80 steps. When the counter runs out, the lit area loses two tiles in each direction and the counter starts again at 60. So RADIANT gives 80 steps at 7 by 7, then 60 at 5 by 5, then 60 at 3 by 3. After that only your own tile is lit.

REPEL and Fairy Water share one counter. REPEL sets it to 255 and Fairy Water to 254, and every step takes 2 off. Both last 127 steps. The odd and the even start let the game tell them apart when the counter ends, so it can print the right message.

Wings do not work inside a cave. The check is at $DD73.

## 11. What the two best armors do

Magic Armor has the same defense as Full Plate. Its extra is a step counter: on every fourth step you get one hit point back, at $CD06. Erdrick's Armor gives one back on every step.

A swamp tile costs 2 hit points and a barrier tile 15. In Erdrick's Armor both cost nothing. Magic Armor does not help here.

When an enemy casts HURT or HURTMORE at you, the game checks your armor at $EC36. In Erdrick's Armor or Magic Armor it divides the damage by three, drops the remainder and doubles the result, so you take about two thirds. Fire breath gets the same cut at $ECFC, but in Erdrick's Armor only.

An enemy's STOPSPELL works one time in two. Against Erdrick's Armor it never works.

## 12. The Fighter's Ring sets a flag that nothing uses

Putting on the Fighter's Ring sets one bit at address $CF, at $DFD1. In the whole cartridge that bit is read in one other place, at $D2BF: the dialog of a townsman who remarks on the ring. The routine that works out your attack power takes your strength and the weapon table and never looks at it.

The Dragon's Scale is the opposite case. It also sets a bit at $CF, and the routine at $F0FE that works out your defense adds 2 when that bit is set.

The two cursed items set bits there as well. While either is set, a game you load starts you with 1 hit point, at $CB6B.

## One more, for map makers

The maps are packed two ways. Maps with a number below 12 use four bits for each tile. Maps from 12 up use three bits. The dungeon tile set starts only at map 15, so the cellar of Tantegel and the two shrines, maps 12 to 14, are three-bit maps drawn with the town tiles.

## Sources

The addresses refer to the code of Dragon Warrior (USA), first release. The memory locations agree with the public RAM map of the game's disassembly by nmikstas. The routines for spells, items and armor were found with the same disassembly, and their bytes were then read from the cartridge. The enemy numbers were read from the cartridge. [Retro Companion](/) uses these same rules to show enemy stats and your damage range during a fight.
