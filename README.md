<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

<p align="center">
  <strong>A digital companion for adventures in Kreijor.</strong>
</p>

<p align="center">
  Character Management · Rules Automation · Equipment · Magic · Progression
</p>

<p align="center">
  English · <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  <a href="https://discord.gg/mRKwGSsPEG">
    <img src="https://img.shields.io/badge/Discord-Join%20the%20Community-5865F2?logo=discord&logoColor=white" alt="Discord">
  </a>
  <img src="https://img.shields.io/badge/Version-0.18.1--beta-purple" alt="Version 0.18.1-beta" />
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/License-PolyForm%20Noncommercial%201.0.0-blue" alt="PolyForm Noncommercial 1.0.0">
</p>

---

# Codex Arcana

**Codex Arcana** is an unofficial digital companion for the German dark-fantasy pen-and-paper RPG **Arcane Codex**.

It started with a simple idea:

> A digital character sheet should do more than store numbers.

A character in Arcane Codex is shaped by attributes, skills, advantages and disadvantages, combat and magic schools, equipment, wounds, armor, spells, divine powers, experience, resources and countless interactions between them.

Keeping all of that synchronized by hand can become quite a task.

**Codex Arcana aims to take care of that bookkeeping.**

The project combines character management with an integrated rules engine so that the sheet reacts to what is actually happening to the character.

Equip a weapon and its values become available.  
Put on armor and its protection becomes part of the character.  
Learn a school and new progression options become available.  
Gain an advantage and its effects can influence the appropriate values and rules.  
Cast a spell and the character's Arcane Power is actually spent.

The goal is not to replace the tabletop, the players, the game master, or the rulebooks.

The goal is to let the software deal with the paperwork while everyone else gets on with the adventure.

---

## ✦ What Codex Arcana wants to be

Codex Arcana is being developed as a complete digital home for an Arcane Codex character — from the first idea during character creation to a veteran adventurer carrying years of scars, equipment, magic, experience and questionable life decisions.

Rather than building a collection of isolated calculators, the project tries to connect the different parts of the game.

A character's equipment should matter to their sheet.

Their advantages and disadvantages should matter to their values.

Their schools should determine what they may learn.

Their wounds should affect them.

Their magic should consume actual resources.

And when something changes, the rest of the character should follow automatically wherever possible.

That is the central idea behind Codex Arcana.

---

## ✦ Current State

> **Codex Arcana is currently in Beta.**

The project is actively developed and already covers a considerable part of character management and gameplay, but it is not feature-complete.

Rules coverage continues to grow, interfaces are still being refined, and parts of the internal structure may change as increasingly exotic corners of Arcane Codex inevitably emerge from the shadows.

And there are quite a few shadows.

The current focus is not merely on reproducing the paper character sheet, but on gradually teaching the application how the game itself works.

---

# ✦ Character Creation

Codex Arcana includes a multi-phase character creation system designed around the actual structure of an Arcane Codex character.

Character creation can handle areas such as:

- race
- attributes
- skills
- advantages and disadvantages
- languages
- schools
- specializations
- character-specific choices
- starting equipment and resources
- character origin
- skill and trait specifications

Creation is not treated as a simple form.

Selections can be validated against character-building rules and dependencies so that the resulting character enters the main application as an actual playable character rather than merely a collection of submitted values.

Drafts can also be preserved so that a character does not need to be created in a single sitting.

---

# ✦ The Character Sheet

The character sheet is the heart of Codex Arcana.

It brings together the current state of the character and presents the values that matter during play.

Depending on the character, this includes areas such as:

- attributes and derived values
- skills and specializations
- advantages and disadvantages
- combat values
- wounds
- Arcane Power
- schools and techniques
- magic
- equipment
- armor
- weapons
- currency
- progression
- personal character information

The sheet is not intended to simply reproduce the printed character sheet pixel by pixel.

Instead, it is designed as an interactive interface that can expose additional information when it becomes relevant while keeping the everyday view compact enough to remain useful during an actual game session.

---

# ✦ Combat

Combat support is gradually becoming one of the larger parts of Codex Arcana.

The application can work with character combat values and equipment rather than leaving every calculation to the player.

Current systems include support for areas such as:

- initiative
- defenses and resistances
- wounds and wound penalties
- melee weapons
- ranged weapons
- shields
- armor
- equipment-based modifiers
- damage calculations
- weapon-specific attributes
- minimum strength requirements

Ranged weapons have their own profiles including range bands, ammunition and reload information.

Shields are not necessarily passive pieces of armor either: where the rules allow it, they can also function as offensive weapons.

The armor interface includes an interactive body map so that protection can be presented according to the relevant body zones instead of being reduced to a single anonymous number.

The long-term aim is for the character sheet to provide the values a player actually needs at the table without requiring them to reconstruct those values manually from half a dozen different rules.

---

# ✦ Equipment & Inventory

A heroic career tends to accumulate things.

Weapons. Armor. Shields. Coins. Magical objects. Strange relics. Things someone found in a crypt and absolutely should not have touched.

Codex Arcana includes a persistent inventory and equipment system that distinguishes between simply owning an item and actually using it.

Equipment can carry mechanical information such as:

- weight
- price
- quality
- armor values
- weapon values
- damage
- ranges
- minimum strength
- modifiers
- magical effects
- character-specific modifications

The system is increasingly moving toward items whose mechanical effects are understood by the application rather than existing only as descriptive text.

This makes it possible for equipment to influence the character directly when appropriate.

---

# ✦ Armor

Armor in Arcane Codex deserves more than a checkbox.

Codex Arcana supports equipment-based armor handling and an interactive body-zone display that allows the character sheet to present protection in a more immediately readable form.

Different pieces of armor can contribute to the actual defensive state of the character while encumbrance and other relevant properties remain part of the calculation.

The goal is to make questions such as

> "What protection do I actually have there?"

answerable by looking at the sheet instead of beginning a small archaeological expedition through notes and equipment tables.

---

# ✦ Magic

Magic is not implemented as an isolated mini-application.

Arcane and divine magic are connected to the same character progression system as the rest of Codex Arcana.

Characters can gain access to spells through their schools, aspects and other sources, while the application keeps track of why a character knows a particular spell.

Current magic support includes:

- arcane schools
- divine schools
- divine entities
- divine aspects
- base spells
- automatically granted spells
- freely selected spells
- additionally learned spells
- bonus spell sources
- spell availability
- spell progression
- casting validation
- Arcane Power consumption

A spell displayed on the character sheet is therefore not merely decorative.

When a character casts through Codex Arcana, the backend validates whether the character actually knows the spell and has enough Arcane Power before spending the corresponding KP.

The sheet is then updated accordingly.

The aim is simple:

**If Codex Arcana says your character can cast it, the application should know why.**

---

# ✦ Divine Characters

Clerical characters receive their own integration into the magic system rather than being treated as slightly unusual arcane spellcasters.

Codex Arcana can represent the relationship between:

- divine schools
- the worshipped divine entity
- granted aspects
- additional aspects
- aspect progression
- divine spell knowledge

This allows divine progression to grow together with the character while preserving the distinction between automatic grants and things the character has deliberately learned or purchased.

---

# ✦ Schools, Techniques & Progression

Characters in Arcane Codex rarely remain the people they were when their journey began.

Codex Arcana therefore includes progression systems for:

- attributes
- skills
- languages
- combat schools
- magic schools
- school paths
- techniques
- specializations
- spells

The application tracks character progression as persistent state rather than simply allowing arbitrary values to be typed into the sheet.

Where possible, requirements, exclusions and progression rules are taken into account when determining what is available to a character.

The eventual goal is a learning system where character development feels like an extension of the game rather than database administration with prettier buttons.

---

# ✦ Advantages, Disadvantages & Rule Effects

One of the more difficult parts of Arcane Codex is that advantages and disadvantages do much more than provide simple numerical bonuses or penalties.

Some modify skills.

Some change resources.

Some grant immunities or capabilities.

Some alter movement or combat.

Some change social interaction.

Some only apply under very specific circumstances.

Others cheerfully ignore the idea of being represented by a number at all.

Codex Arcana therefore treats rule effects as more than `+2` and `-4`.

The rules system is being built to understand different kinds of effects and apply them to the character where they belong.

This is one of the project's most important foundations: as rules coverage grows, increasingly complex character abilities can become part of the actual sheet instead of surviving forever as tooltip text followed by:

> "Remember to add this yourself."

---

# ✦ Money & Economy

Codex Arcana also keeps track of character wealth.

Currency can be presented in a compact format while still providing conversions between the different denominations when needed.

Item prices, quality and other economic rules can therefore remain connected to the inventory rather than requiring a second accounting system beside the character sheet.

Because apparently defeating demons is not enough. Someone still has to pay the tavern bill.

---

# ✦ Character Details & Personalization

Not everything about a character is combat mathematics.

Codex Arcana also preserves character-side information and longer-running personal data, including areas such as:

- character origin
- custom skill specifications
- custom trait specifications
- diary entries
- persistent character information

Where the rules require a skill or trait to describe something specific, Codex Arcana can store that specification for the individual character rather than forcing every instance into a generic global definition.

---

# ✦ DDDice Integration

Codex Arcana can integrate with **DDDice** for animated 3D dice.

The visual dice are deliberately separated from the authoritative game result.

The result itself is determined by Codex Arcana on the server.

DDDice provides the spectacle.

So the shiny tumbling polyhedra may have all the drama — but they do not get to quietly rewrite reality when nobody is looking.

---

# ✦ Built for the Table

Codex Arcana is ultimately meant to be used while playing.

That influences a lot of design decisions.

The interface should expose detailed information when a player wants it without permanently filling the screen with every possible rule explanation.

Frequently used information should remain immediately available.

Complex calculations should happen automatically.

And character data should remain persistent between sessions.

The ambition is not to digitize the rulebook page by page.

It is to create the digital character companion that can sit beside those books at the table.

---

# ✦ Community

Codex Arcana is a hobby project, and feedback from people who actually know and play Arcane Codex is particularly valuable.

Want to follow development, discuss features, report something bizarre, suggest improvements or simply talk about Arcane Codex?

Join the Discord:

<p align="center">
  <a href="https://discord.gg/mRKwGSsPEG">
    <strong>⚔ Join the Codex Arcana Discord ⚔</strong>
  </a>
</p>

Development previews, discussions and the occasional discovery of yet another beautifully obscure rules interaction are welcome there.

Bug reports and development tasks can also be tracked through the GitHub issue system.

---

# ✦ For Developers

Codex Arcana is a server-side web application built primarily with:

- **Python 3**
- **Django 6.0**
- **PostgreSQL 16**
- **Django Templates**
- JavaScript and CSS for the interactive character interface

The rules architecture is deliberately kept on the server wherever possible.

The browser is responsible for interaction and presentation, while authoritative character state and game-rule calculations remain in the backend.

This avoids turning the character sheet into two competing rules engines — one in Python and one hiding somewhere in JavaScript waiting for the worst possible moment to disagree.

---

## Project Structure

A simplified overview:

```text
codex_arcana/

charsheet/
├── models/
├── engine/
├── modifiers/
├── templates/
└── sheet_context.py

docs/
static/
```

More detailed implementation documentation can be found in:

- [`docs/engine.md`](docs/engine.md)
- [`docs/models.md`](docs/models.md)
- [`docs/modifier_refactor.md`](docs/modifier_refactor.md)

---

# ✦ Running Codex Arcana Locally

## Requirements

You will need:

- Python 3
- PostgreSQL 16

A Docker configuration for the development database is included.

### Start PostgreSQL

```bash
docker compose up -d db
```

### Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### Apply database migrations

```bash
python manage.py migrate
```

### Create an administrator account

```bash
python manage.py createsuperuser
```

### Start the development server

```bash
python manage.py runserver
```

Codex Arcana should then be available at:

```text
http://127.0.0.1:8000/
```

The Django administration interface is available at:

```text
http://127.0.0.1:8000/admin/
```

---

# ✦ Development Status & Contributions

Codex Arcana is under active development.

New rule areas are added incrementally, existing systems are refined as they encounter more of the original rules, and both the interface and internal architecture continue to evolve.

Issues and contributions are welcome.

Because this is an Early Alpha project, however, compatibility between development versions is not guaranteed.

For discussion before opening an issue or when you are unsure whether something is a bug, a missing rule or simply Arcane Codex being Arcane Codex, the Discord server is usually a good place to start.

---

# ✦ About Arcane Codex

**Arcane Codex** is a German dark-fantasy pen-and-paper role-playing game set in the world of Kreijor.

Codex Arcana is a fan-made companion application and is **not an official Arcane Codex product**.

It does not replace the Arcane Codex rulebooks and is intended to be used together with legally acquired copies of the official game material.

For information about Arcane Codex and its official publications, visit:

**[Nackter Stahl Verlag](https://www.nackterstahl.de/)**

---

# ✦ Copyright, Fan Content & Legal Notice

**Codex Arcana** is an unofficial fan-made companion application for the
pen-and-paper role-playing game **Arcane Codex**.

The project is not affiliated with, published by, sponsored by, or endorsed by
Nackter Stahl Verlag or the rights holders of Arcane Codex.

## Arcane Codex

**Arcane Codex**, **Nackter Stahl**, **Die Stählernen Königreiche**, the
**2w10 System**, and the associated setting, characters, locations, terminology,
game material, artwork, designs and other protected elements remain the property
of their respective rights holders.

Official Arcane Codex publications identify the relevant game material as
copyrighted by **Saskia Maucher / Nackter Stahl Verlag, Köln**.

Codex Arcana does not claim ownership of the Arcane Codex setting or the
underlying intellectual property on which the application is based.

The project is intended to complement legally acquired Arcane Codex
publications and is not intended to replace or redistribute the original
rulebooks.

## Visual Assets

Codex Arcana contains visual assets created specifically for this project.

Some of these assets are original interpretations of characters, creatures,
items, locations, symbols or other concepts described in Arcane Codex.

Some project artwork may also visually reference or draw inspiration from
illustrations and designs found in official Arcane Codex publications.

Unless explicitly identified as an original Codex Arcana design, no ownership
of the underlying Arcane Codex characters, concepts, designs or other protected
material is claimed.

Where newly created artwork is based on or closely references protected
Arcane Codex material, all rights in the underlying material remain with the
respective rights holders.

Codex Arcana does not distribute digital copies of the Arcane Codex rulebooks
or source publications.

## Source Code

The original **Codex Arcana application source code** is licensed under the
**PolyForm Noncommercial License 1.0.0**.

The source code may be used, studied, modified and shared for private,
personal, educational, hobbyist and other noncommercial purposes in accordance
with the terms of that license.

**Commercial use is not permitted under the PolyForm Noncommercial License.**

Companies, organizations or individuals wishing to use Codex Arcana for
commercial purposes may contact the copyright holder to negotiate a separate
commercial license.

See [`LICENSE`](LICENSE) for the complete license terms.

This license applies exclusively to the original Codex Arcana software source
code and does **not** grant rights to third-party intellectual property,
including Arcane Codex material, trademarks, artwork, characters, settings,
game rules or other protected content referenced or represented by the project.