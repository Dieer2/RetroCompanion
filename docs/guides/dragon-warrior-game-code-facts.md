title: Eight things the code of Dragon Warrior says about how the game works
description: What happens when you die, why level 30 stops at 65,535, how damage is worked out, and other rules of Dragon Warrior read from the game's own code and memory.
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

## One more, for map makers

The maps are packed two ways. Maps with a number below 12 use four bits for each tile. Maps from 12 up use three bits. The dungeon tile set starts only at map 15, so the cellar of Tantegel and the two shrines, maps 12 to 14, are three-bit maps drawn with the town tiles.

## Sources

The addresses refer to the code of Dragon Warrior (USA), first release. The memory locations agree with the public RAM map of the game's disassembly by nmikstas. The enemy numbers were read from the cartridge. [Retro Companion](/) uses these same rules to show enemy stats and your damage range during a fight.
