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
from utils.birthday_db import init_birthday_db


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

    # Wichtig: config._data direkt überschreiben (internes Dict!)
    config._data["guild_id"] = 1460995865329270964 # ← Testserver ID

    # Log-Channels
    config._data.setdefault("log_channels", {})
    config._data["log_channels"]["bot"] = 1460995867334017169 
    config._data["log_channels"]["moderation"] = 1461013968335409388 
    config._data["channels"]["member_count_vc"] = 1460995866381779039 # Member Count VC
    config._data["channels"]["welcome_channel"] = 1460995866381779043 # Welcome Channel
    config._data["twitch"]["announce_channel"] = 1460995866381779046 # Twitch Ankündigungen (für API)
    config._data["channels"]["rules_channel"] = 1460995866381779041 # Regeln Channel

    # Status Channels
    config._data["channels"]["bot_status"] = 1487418133839872091
    config._data["channels"]["dashboard_status"] = 1487418186314940428

    # Tickets
    config._data.setdefault("tickets", {})
    config._data["tickets"]["enabled"] = True
    config._data["tickets"]["category_open"] = 1469741779346657425 
    config._data["tickets"]["category_closed"] = 1469741852507766927

    # Roles
    config._data.setdefault("roles", {})
    config._data["roles"]["bot"] = 1461009559048032361
    config._data["roles"]["owner"] = 1460995865731793089
    config._data["roles"]["co_owner"] = 1460995865731793088
    config._data["roles"]["admin"] = 1460995865731793086
    config._data["roles"]["moderator"] = 1460995865731793085
    config._data["roles"]["dev"] = 1464688329491484792
    config._data["roles"]["supporter"] = 1460995865731793084
    config._data["roles"]["member_1"] = 1460995865329270968
    config._data["roles"]["member_2"] = 1460995865329270969
    config._data["roles"]["member_3"] = 1460995865329270970
    config._data["roles"]["member_4"] = 1460995865329270971

    # Features
    config._data.setdefault("features", {})
    config._data["features"]["admin"]                 = True
    config._data["features"]["dev"]                   = True
    config._data["features"]["fun"]                   = True
    config._data["features"]["moderation"]            = True
    config._data["features"]["roles"]                 = True
    config._data["features"]["tickets"]               = True   # ← zum Debuggen True
    config._data["features"]["twitch"]                = True
    config._data["features"]["member_count"]          = True
    config._data["features"]["welcome"]               = True
    config._data["features"]["rules_reaction"]        = True
    config._data["features"]["automod"]              = True
    config._data["features"]["birthday"]              = True
    config._data["features"]["status_channels"]      = True

    #automod
    config._data.setdefault("automod", {})
    config._data["automod"]["enabled"] = True
    #rules:
    config._data.setdefault("rules", {})
    config._data["rules"]["message_id"] = 1477895408780050554
    config._data["rules"]["reaction_role"] = "member_1" # ← Role, die vergeben wird, wenn User auf Regeln reagiert (z.B. mit ✅)

    #birthday
    config._data.setdefault("birthday", {})
    config._data["birthday"]["enabled"] = True
    config._data["features"]["birthday"] = True
    config._data["birthday"]["channel_id"] = 1483841274120503365 # ← Birthday Channel

    logger.info("Dev-Modus: Alle Features & Test-IDs aktiviert – Chaos erlaubt! 🚧")

else:
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
intents.message_content = True
intents.members = True
intents.reactions = True

init_db()
init_birthday_db()
class ChaosBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        # Alle Cogs mit ihrer Ladebedingung
        cogs = {
            "admin":            config.features.get("admin", False),
            "fun":              config.features.get("fun", False),
            "roles":            config.features.get("roles", False),
            "moderation":       config.features.get("moderation", False),
            "tickets":          config.tickets.get("enabled", False),
            "dev":              True,  # ← immer laden für Sync & Debugging
            "welcome":          config.features.get("welcome", False), # ← Welcome nur laden, wenn aktiviert
            "twitch_live":      config.features.get("twitch_notifications", False), # ← Twitch Benachrichtigungen nur laden, wenn aktiviert
            "member_count":     config.features.get("member_count", False), # ← Member Count nur laden, wenn aktiviert
            "rules_reaction":   config.features.get("rules_reaction", False), # ← Rules Reaction nur laden, wenn aktiviert
            "auto_handler":     config.features.get("automod", False), # ← AutoMod nur laden, wenn aktiviert
            "birthday":         config.features.get("birthday", False), # ← Birthday nur laden, wenn aktiviert
            "status_channels":  config.features.get("status_channels", False), # ← Status Channels nur laden, wenn aktiviert

        }

        loaded_cogs = []
        failed_cogs = []

        for cog_name, should_load in cogs.items():
            if should_load:
                try:
                    await self.load_extension(f"cogs.{cog_name}")
                    loaded_cogs.append(cog_name)
                    logger.info(f"Cog '{cog_name}' geladen")
                except Exception as e:
                    logger.error(f"Fehler beim Laden von '{cog_name}': {e}")
                    failed_cogs.append(cog_name)
            else:
                logger.info(f"Cog '{cog_name}' übersprungen – Feature deaktiviert")
        #Zusammenfassung in Log
        logger.info(f"✅ Cogs geladen: {', '.join(loaded_cogs) if loaded_cogs else 'Keine'}")
        if failed_cogs:
            logger.warning(f"⚠️ Cogs mit Fehlern: {', '.join(failed_cogs)}")
            
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