<p align="center">
  <img src="static/img/codexarcana.png" alt="Codex Arcana Logo" width="560">
</p>

<p align="center">
  🇬🇧 English | 🇩🇪 <a href="README.de.md">Deutsch</a>
</p>

# Codex Arcana

> ⚠️ **Status: Early Alpha / Prototype**  
> This project is currently in an early development stage. Features may be incomplete, unstable, or subject to change without notice.

Codex Arcana is a Django-based management system for the pen-and-paper role-playing game **Arcane Codex**. The application combines classic character management with a rule-driven engine, ensuring that a character sheet does not merely store data but consistently calculates game-relevant values based on the current state.

---

## Current Features

- Dashboard with active characters, archive, draft management, and account settings  
- Multi-phase character creation with persistent drafts  
- Character sheet with precomputed template context  
- Inventory, equipment, and quality-dependent item values  
- Learning system using experience points for attributes, skills, languages, and schools  
- Shop with cart system, price calculation, and custom items  
- Persistent character diary with JSON endpoints for the UI  
- Technique, specialization, and modifier system for rule-driven unlocks  

---

## Technology Stack

- Python 3  
- Django 5.2  
- PostgreSQL 16  
- Django Templates  
- Global assets in `static/`, app-specific assets in `charsheet/static/`  

---

## Getting Started

### Requirements

- Python 3.x  
- PostgreSQL running on `localhost:5432`  
- alternatively Docker for the provided database setup  

### Start database via Docker

docker compose up -d db

### Run application

python -m pip install -r requirements.txt  
python manage.py migrate  
python manage.py createsuperuser  
python manage.py runserver  

### Important URLs

- Login: `http://127.0.0.1:8000/`  
- Admin: `http://127.0.0.1:8000/admin/`  

---

## Overview

The following views provide a quick impression of the current state of the application. All preview images are clickable.

---

## Application Tutorial

This tutorial describes the main workflow currently supported by the system.

### 1. Login

1. Open `http://127.0.0.1:8000/`  
2. Log in with your account  
3. After successful login, you will be redirected to the dashboard  

### 2. Understanding the Dashboard

The dashboard contains several functional areas:

- **User section** with logout and account settings  
- **Recently used** for quick access to characters  
- **System status** showing global data (items, skills, schools, languages)  
- **Notifications** for unspent EP, open damage, or other conditions  
- **Open drafts** for unfinished character creation  
- **Character management** for active characters  
- **Archive** for inactive characters  

### 3. Creating a New Character

1. Click **New Character**  
2. The creation process opens as an overlay  
3. Work through the phases step by step  
4. Drafts are saved automatically  
5. Finalizing creates the full character with all related data  

### 4. Opening an Existing Character

1. Select a character in the **Character Management** table  
2. Click **Open**  
3. The character sheet displays the full current state  

### 5. Working with the Character Sheet

The character sheet is the central interface of the application:

- Attributes and skills with rule-based calculations  
- Advantages, disadvantages, languages, schools, and techniques  
- Weapons, armor, and inventory management  
- Money, experience, damage, and reputation tracking  
- Learning interface, shop, and diary  

---

## Project Structure

codex_arcana/  
charsheet/  
  models/  
  engine/  
  templates/  
  learning.py  
  shop.py  
  sheet_context.py  
  view_utils.py  
static/  
docs/  

---

## 🎲 DDDice Integration

Codex Arcana uses **DDDice** to render animated 3D dice in the browser.

The actual dice logic is calculated entirely on the **server side**.  
DDDice is used purely for visual representation.

This ensures that the dice system is:

- fully rule-compliant with Arcane Codex  
- deterministic and server-controlled  
- not manipulable on the client side  
- visually enhanced with 3D dice animations  

---

### Why DDDice is used

DDDice provides a visual layer without shifting game logic into the browser.

Workflow:

1. User triggers a dice roll  
2. Frontend sends a request to the backend  
3. Backend calculates the result  
4. Result is returned as JSON  
5. DDDice renders the animation based on that result  

---

## Legal Notice

Codex Arcana uses **DDDice**, a third-party service:

https://dddice.com

The integration is optional and only activated via user settings.

When enabled, technical data (such as IP address) may be transmitted to DDDice servers.  
If disabled, no connection is established.

All rights to the DDDice engine remain with its respective owners.

---

## License

This project is licensed under the GNU General Public License v3.0.

Third-party licenses (e.g. fonts in `static/fonts/`) remain unaffected.