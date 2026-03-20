# 🤖 ChaosBot

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord)
![License](https://img.shields.io/badge/License-AGPL%20v3-blue)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

---

> 🇩🇪 [Deutsch](#deutsch) | 🇬🇧 [English](#english)

---

## Deutsch

### 📖 Über den Bot

ChaosBot ist ein vollständiger Discord-Bot gebaut mit **discord.py**, der eine breite Palette an Moderations-, Automatisierungs- und Community-Features bietet. Er ist modular aufgebaut und über eine zentrale `config.yaml` konfigurierbar.

---

### ✨ Features

| Feature | Beschreibung |
|---|---|
| 🤖 **AutoMod** | Automatische Erkennung von Spam, Caps und verbotenen Wörtern mit Auto-Warn |
| ⚠️ **Warning System** | Verwarnungssystem mit automatischen Maßnahmen (Timeout/Kick/Ban) |
| 🎫 **Ticket System** | Ticket-System mit Modals, Kategorien und Archivierung |
| 👥 **Member Count** | Voice Channel der automatisch die Mitgliederzahl anzeigt |
| 👋 **Welcome Messages** | Automatische Willkommensnachrichten bei Server-Beitritt |
| ✅ **Rules Reaction** | Rollenvergabe bei Bestätigung der Serverregeln |
| 🎮 **Twitch Announcements** | Live-Benachrichtigungen wenn ein Streamer live geht |
| 🛡️ **Role Management** | Automatische Rollenverwaltung und Synchronisierung |
| 📋 **Moderation Commands** | Vollständige Moderationskommandos (Warn/Kick/Ban/Timeout etc.) |
| 🔒 **Permission System** | Stufenbasiertes Berechtigungssystem (Member bis Owner) |
| 🎂 **Geburtstags-Reminder** | Geburtstagsreminder, der die Tage in der dB. speichert |

---

### 🔧 Bot Permissions

Folgende Berechtigungen werden für den vollen Funktionsumfang benötigt:

| Permission | Benötigt für |
|---|---|
| `Manage Channels` | Member Count VC, Ticket-Erstellung |
| `Manage Roles` | Rollenvergabe (Rules Reaction, Role Management) |
| `Manage Messages` | AutoMod (Nachrichten löschen) |
| `Kick Members` | Auto-Kick, `/kick` Command |
| `Ban Members` | Auto-Ban, `/ban` Command |
| `Moderate Members` | Timeout-Funktionen |
| `Send Messages` | Allgemeine Bot-Nachrichten |
| `Read Message History` | Ticket-System, AutoMod |
| `View Channels` | Allgemein |

**Privileged Gateway Intents (Discord Developer Portal):**
- ✅ Server Members Intent
- ✅ Message Content Intent

---

### ⚙️ Installation & Setup

#### Voraussetzungen
- Python 3.12+
- Docker & Docker Compose (empfohlen)

#### 1. Repository klonen
```bash
git clone https://github.com/CaptinChaot/Discord_Bot.git
cd Discord_Bot
```

#### 2. Umgebungsvariablen setzen
```bash
# Für Produktion
cp .env.example .env

# Für Entwicklung
cp .env.example .env.dev
```

Inhalt der `.env` Datei:
```env
DISCORD_TOKEN=dein_bot_token_hier
BOT_ENV=prod  # oder dev
```

#### 3. `config.yaml` anpassen
Siehe [config.yaml Erklärung](#configyaml-erklärung)

#### 4. Starten
```bash
# Mit Docker
docker compose up -d

# Ohne Docker
pip install -r requirements.txt
python main.py
```

---

### 📝 config.yaml Erklärung

```yaml
# Server ID
guild_id: 123456789

# Rollen-Verwaltung
role_management:
  staff_roles:           # Rollen die als Staff gelten
    - owner
    - moderator
  allowed_roles:         # Rollen die automatisch vergeben werden können
    - member_1

# Rollen IDs
roles:
  owner: 123456789       # Discord Rollen-ID

# Channels
channels:
  welcome_channel: 123456789    # Willkommens-Channel
  member_count_vc: 123456789    # Voice Channel für Mitgliederzahl
  rules_channel: 123456789      # Regelchannel

# Log Channels
log_channels:
  bot: 123456789                # Bot-Log Channel
  moderation: 123456789         # Moderations-Log Channel

# Berechtigungsstufen
# MEMBER=0 / SUPPORT=5 / MOD=10 / ADMIN=20 / DEV=30 / CO_OWNER=35 / OWNER=40
permissions:
  warn:
    min_level: 10        # Mindest-Level für den Command

# Moderation Schwellenwerte
moderation:
  warn_timeout_threshold: 2     # Verwarnungen bis Timeout
  warn_kick_threshold: 3        # Verwarnungen bis Kick
  warn_ban_threshold: 5         # Verwarnungen bis Ban
  warn_timeout_duration: 300    # Timeout-Dauer in Sekunden
  auto_action_cooldown: 60      # Cooldown zwischen Auto-Aktionen in Sekunden

# AutoMod
automod:
  enabled: true
  spam:
    enabled: true
    message_limit: 5     # Nachrichten...
    time_window: 5       # ...in X Sekunden
  caps:
    enabled: true
    threshold: 70        # Prozent Großbuchstaben
    min_length: 10       # Mindestlänge der Nachricht
  blacklist:
    enabled: true
    words:
      - "verbotenesWort"

# Regeln Reaction
rules:
  message_id: 123456789         # ID der Regelnachricht
  reaction_role: member_1       # Rolle die vergeben wird

# Ticket System
tickets:
  enabled: true
  category_open: 123456789      # Kategorie für offene Tickets
  category_closed: 123456789    # Kategorie für archivierte Tickets
  support_min_level: 5          # Mindest-Level für Support
  channel_prefix: "ticket"      # Prefix für Ticket-Channel Namen
  archive:
    hide_from_user: true        # User sieht archiviertes Ticket nicht mehr
    lock_user_message: true
    max_open_per_user: 3        # Max. offene Tickets pro User

# Twitch
twitch:
  client_id: "deine_client_id"
  client_secret: "dein_client_secret"
  username: "twitch_username"
  announce_channel: 123456789   # Channel für Live-Ankündigungen

# Features togglen
features:
  admin: true
  moderation: true
  tickets: true
  member_count: true
  welcome: true
  rules_reaction: true
  automod: true
  twitch_notifications: true
```

---

### 💬 Commands Übersicht

| Command | Beschreibung | Mindest-Level |
|---|---|---|
| `/warn` | User verwarnen | MOD (10) |
| `/warnings` | Verwarnungen anzeigen | SUPPORT (5) |
| `/unwarn` | Letzte Verwarnung löschen | MOD (10) |
| `/delete_warnings` | Alle Verwarnungen löschen | ADMIN (20) |
| `/timeout` | User in Timeout setzen | MOD (10) |
| `/untimeout` | Timeout entfernen | MOD (10) |
| `/kick` | User kicken | ADMIN (20) |
| `/ban` | User bannen | ADMIN (20) |
| `/unban` | User entbannen | ADMIN (20) |
| `/clear` | Nachrichten löschen | MOD (10) |
| `/userinfo` | User-Informationen anzeigen | SUPPORT (5) |
| `/sync_user` | DB mit Discord synchronisieren | DEV (30) |
| `/send_ticket_panel` | Ticket-Panel senden | DEV (30) |
| `/set_birthday` | Geburtstag setzen | MEMBER |
| `/birthday` | Geburtstag einsehen | MEMBER |

---

### 🤝 Contributing

Pull Requests sind willkommen! Bitte beachte folgende Punkte:

1. Forke das Repository
2. Erstelle einen neuen Branch (`git checkout -b feature/mein-feature`)
3. Halte dich an die bestehende Code-Struktur (Cogs, Utils, Config)
4. Teste deine Änderungen auf einem Dev-Server
5. Erstelle einen Pull Request mit einer klaren Beschreibung

---

---

## English

### 📖 About the Bot

ChaosBot is a full-featured Discord bot built with **discord.py**, offering a wide range of moderation, automation, and community features. It is modular and configurable via a central `config.yaml`.

---

### ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AutoMod** | Automatic detection of spam, caps and blacklisted words with auto-warn |
| ⚠️ **Warning System** | Warning system with automatic actions (Timeout/Kick/Ban) |
| 🎫 **Ticket System** | Ticket system with modals, categories and archiving |
| 👥 **Member Count** | Voice channel that automatically displays the member count |
| 👋 **Welcome Messages** | Automatic welcome messages when a user joins |
| ✅ **Rules Reaction** | Role assignment upon confirmation of server rules |
| 🎮 **Twitch Announcements** | Live notifications when a streamer goes live |
| 🛡️ **Role Management** | Automatic role management and synchronization |
| 📋 **Moderation Commands** | Full moderation commands (Warn/Kick/Ban/Timeout etc.) |
| 🔒 **Permission System** | Level-based permission system (Member to Owner) |
| 🔒 **Birthday-Reminder** | Birthday-Reminder - saves Days in the dB |


---

### 🔧 Bot Permissions

The following permissions are required for full functionality:

| Permission | Required for |
|---|---|
| `Manage Channels` | Member Count VC, Ticket creation |
| `Manage Roles` | Role assignment (Rules Reaction, Role Management) |
| `Manage Messages` | AutoMod (deleting messages) |
| `Kick Members` | Auto-Kick, `/kick` command |
| `Ban Members` | Auto-Ban, `/ban` command |
| `Moderate Members` | Timeout functions |
| `Send Messages` | General bot messages |
| `Read Message History` | Ticket system, AutoMod |
| `View Channels` | General |

**Privileged Gateway Intents (Discord Developer Portal):**
- ✅ Server Members Intent
- ✅ Message Content Intent

---

### ⚙️ Installation & Setup

#### Requirements
- Python 3.12+
- Docker & Docker Compose (recommended)

#### 1. Clone the repository
```bash
git clone https://github.com/CaptinChaot/Discord_Bot.git
cd Discord_Bot
```

#### 2. Set environment variables
```bash
# For production
cp .env.example .env

# For development
cp .env.example .env.dev
```

Content of the `.env` file:
```env
DISCORD_TOKEN=your_bot_token_here
BOT_ENV=prod  # or dev
```

#### 3. Configure `config.yaml`
See [config.yaml explanation](#configyaml-explanation)

#### 4. Start the bot
```bash
# With Docker
docker compose up -d

# Without Docker
pip install -r requirements.txt
python main.py
```

---

### 📝 config.yaml Explanation

See the German section above for a fully annotated `config.yaml` – all keys and comments are self-explanatory.

---

### 💬 Commands Overview

| Command | Description | Minimum Level |
|---|---|---|
| `/warn` | Warn a user | MOD (10) |
| `/warnings` | Show warnings | SUPPORT (5) |
| `/unwarn` | Delete last warning | MOD (10) |
| `/delete_warnings` | Delete all warnings | ADMIN (20) |
| `/timeout` | Put user in timeout | MOD (10) |
| `/untimeout` | Remove timeout | MOD (10) |
| `/kick` | Kick a user | ADMIN (20) |
| `/ban` | Ban a user | ADMIN (20) |
| `/unban` | Unban a user | ADMIN (20) |
| `/clear` | Delete messages | MOD (10) |
| `/userinfo` | Show user information | SUPPORT (5) |
| `/sync_user` | Sync DB with Discord | DEV (30) |
| `/send_ticket_panel` | Send ticket panel | DEV (30) |
| `/set_birthday` | Set your Birthday | MEMBER |
| `/birthdayl` | Watch your Birthday | MEMBER |

---

### 🤝 Contributing

Pull requests are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/my-feature`)
3. Follow the existing code structure (Cogs, Utils, Config)
4. Test your changes on a dev server
5. Create a pull request with a clear description
