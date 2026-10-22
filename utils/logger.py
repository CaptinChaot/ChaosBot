import logging
from pathlib import Path
import discord

# --- file path ---
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"

# --- create our own logger (do NOT rely on basicConfig) ---
logger = logging.getLogger("ChaosBot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(sh)

# prevent double logs if root logger also prints
logger.propagate = False


async def log_to_channel(
    bot: discord.Client,
    channel_id: int,
    title: str,
    description: str = "",
    color: discord.Color = discord.Color.blurple(),
    embed: discord.Embed | None = None,
):
    if not channel_id or channel_id == 0:
        logger.warning("Log-Channel-ID ist 0/leer (config.yaml). Kein Embed gesendet.")
        return

    channel = bot.get_channel(channel_id)

    # If not cached, fetch it (more reliable)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.warning(f"Log-Channel {channel_id} nicht abrufbar: {type(e).__name__}: {e}")
            return

    # Wenn schon ein fertiges Embed übergeben wurde (z.B. von /warn), das nehmen
    if embed is None:
        embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="ChaosBot Logger")

    try:
        await channel.send(embed=embed)
    except Exception as e:
        logger.warning(f"Embed konnte nicht gesendet werden: {type(e).__name__}: {e}")
