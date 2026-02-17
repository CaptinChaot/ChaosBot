import os
import asyncio
import discord
import threading
import uvicorn

from api.app import create_api
from discord.ext import commands
from dotenv import load_dotenv
from utils.logger import logger, log_to_channel
from utils.hardening import STAFF_ROLE_IDS
from utils.config import config
from discord import app_commands
from utils.warnings_db import init_db

# ──────────────────────────────────────────────
# 1. Umgebung erkennen & .env laden
# ──────────────────────────────────────────────

bot_env = os.getenv("BOT_ENV", "dev").lower()

if bot_env == "prod":
    load_dotenv(".env")
    logger.info("🚀 Prod-Modus aktiviert (Hauptserver)")
else:
    load_dotenv(".env.dev")
    logger.info("🛠️ Dev-Modus aktiviert (Testserver)")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN fehlt in der geladenen .env-Datei!")

os.environ["BOT_ENV"] = bot_env

# ──────────────────────────────────────────────
# 2. Env-spezifische Overrides (nur Dev überschreibt!)
# ──────────────────────────────────────────────

if bot_env == "dev":
    logger.info("Dev-Overrides: Test-IDs + volle Features")

    # Test-Guild-ID
    config.guild_id = 1460995865329270964

    # Log-Channels
    config.log_channels = config.get("log_channels", {})
    config.log_channels["bot"] = 1460995867334017169
    config.log_channels["moderation"] = 1461013968335409388

    # Tickets – immer an + Test-Kategorien
    config.tickets = config.get("tickets", {})
    config.tickets["enabled"] = True
    config.tickets["category_open"] = 1469741779346657425
    config.tickets["category_closed"] = 1469741852507766927

    # Roles – Test-IDs
    config.roles = config.get("roles", {})
    config.roles["bot"] = 1461009559048032361
    config.roles["owner"] = 1460995865731793089
    config.roles["co_owner"] = 1460995865731793088
    config.roles["admin"] = 1460995865731793086
    config.roles["moderator"] = 1460995865731793085
    config.roles["dev"] = 1464688329491484792
    config.roles["supporter"] = 1460995865731793084
    config.roles["member_1"] = 1460995865329270968
    config.roles["member_2"] = 1460995865329270969
    config.roles["member_3"] = 1460995865329270970
    config.roles["member_4"] = 1460995865329270971

    # Features: In Dev ALLES aktivieren
    config.features = config.get("features", {})
    config.features["admin"]                 = True
    config.features["dev"]                   = True
    config.features["fun"]                   = True
    config.features["moderation"]            = True
    config.features["roles"]                 = True
    config.features["tickets"]               = True   # ← zum Debuggen True
    config.features["twitch_notifications"]  = False

    logger.info("Dev-Modus: Alle Features & Test-IDs aktiviert – Chaos erlaubt! 🚧")

else:
    # Prod: KEINE weiteren Überschreibungen!
    # Der Bot nimmt 1:1 die Werte aus config.yaml
    # Wenn du in YAML moderation: false setzt → lädt nicht
    # Wenn true → lädt
    logger.info("Prod-Modus: 100% config.yaml-Werte – keine erzwungenen Änderungen")

# STAFF_ROLE_IDS neu bauen (nach Overrides!)
STAFF_ROLE_IDS.clear()
for key in config.role_management.get("staff_roles", []):
    role_id = config.roles.get(key)
    if role_id:
        STAFF_ROLE_IDS.add(int(role_id))

# ──────────────────────────────────────────────
# Bot-Setup
# ──────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = False

init_db()

class ChaosBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        cogs = {
            "admin":       config.features.get("admin", False),
            "fun":         config.features.get("fun", False),
            "roles":       config.features.get("roles", False),
            "moderation":  config.features.get("moderation", False),
            "tickets":     config.tickets.get("enabled", False),
            "dev":         True,
        }

        for cog_name, enabled in cogs.items():
            if enabled:
                try:
                    await self.load_extension(f"cogs.{cog_name}")
                    logger.info(f"Cog '{cog_name}' geladen")
                except Exception as e:
                    logger.error(f"Fehler beim Laden von '{cog_name}': {e}")
            else:
                logger.info(f"Cog '{cog_name}' übersprungen – Feature deaktiviert")

        guild = discord.Object(id=config.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info(f"Slash-Commands auf Guild {config.guild_id} gesynct")

bot = ChaosBot()

def start_api(bot):
    app = create_api(bot)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

@bot.event
async def on_ready():
    logger.info(f"✅ Eingeloggt als {bot.user} (ID: {bot.user.id}) | Env: {bot_env.upper()} | Guild: {config.guild_id}")

    if not hasattr(bot, "_api_started"):
        bot._api_started = True
        thread = threading.Thread(target=start_api, args=(bot,), daemon=True)
        thread.start()
        logger.info("🌐 API-Server gestartet.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    root_error = getattr(error, "original", error)
    if isinstance(root_error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
        return
    
    logger.error(f"Fehler bei Slash Command: {root_error}")
    if interaction.response.is_done():
        return

    await interaction.response.send_message("❌ Ein interner Fehler ist aufgetreten.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)