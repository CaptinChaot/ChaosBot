import discord
import time
from collections import defaultdict
from discord.ext import commands
from utils.config import config
from utils.logger import logger, log_to_channel
from utils.warnings_db import add_warning, count_warnings
from utils.moderation_utils import handle_auto_actions
from utils.permissions import get_user_perm_level
from utils.perm_level import PermLevel


class AutoHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.automod_cfg = config.automod

        # Spam-Tracking: {guild_id: {user_id: [timestamps]}}
        self._spam_tracker: dict[int, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    # ─────────────────────────────────────────
    # Haupt-Listener
    # ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.automod_cfg.get("enabled", False):
            return
        if message.author.bot:
            return
        if not message.guild:
            return

        member = message.author

        # Staff überspringen (Supporter+)
        if get_user_perm_level(member) >= PermLevel.SUPPORT:
            return

        triggered, reason = self._check_message(message, member)
        if not triggered:
            return

        # Nachricht löschen
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        await self._auto_warn(message, member, reason)

    # ─────────────────────────────────────────
    # Check-Logik
    # ─────────────────────────────────────────

    def _check_message(self, message: discord.Message, member: discord.Member) -> tuple[bool, str]:
        # 1. Blacklist
        blacklist_cfg = self.automod_cfg.get("blacklist", {})
        logger.info(f"[AutoMod DEBUG] blacklist_cfg: {blacklist_cfg}")    
        if blacklist_cfg.get("enabled", False):
            words = blacklist_cfg.get("words", [])
            content_lower = message.content.lower()
            for word in words:
                if word.lower() in content_lower:
                    return True, f"Verbotenes Wort erkannt"

        # 2. Caps
        caps_cfg = self.automod_cfg.get("caps", {})
        if caps_cfg.get("enabled", False):
            content = message.content
            min_length = caps_cfg.get("min_length", 10)
            threshold = caps_cfg.get("threshold", 70)
            if len(content) >= min_length:
                letters = [c for c in content if c.isalpha()]
                if letters:
                    caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters) * 100
                    if caps_ratio >= threshold:
                        return True, f"Zu viele Großbuchstaben ({caps_ratio:.0f}%)"

        # 3. Spam
        spam_cfg = self.automod_cfg.get("spam", {})
        if spam_cfg.get("enabled", False):
            limit = spam_cfg.get("message_limit", 5)
            window = spam_cfg.get("time_window", 5)
            now = time.time()

            tracker = self._spam_tracker[message.guild.id][member.id]
            tracker.append(now)

            self._spam_tracker[message.guild.id][member.id] = [
                t for t in tracker if now - t <= window
            ]

            if len(self._spam_tracker[message.guild.id][member.id]) >= limit:
                self._spam_tracker[message.guild.id][member.id] = []
                return True, f"Spam ({limit} Nachrichten in {window}s)"

        return False, ""

    # ─────────────────────────────────────────
    # Auto-Warn
    # ─────────────────────────────────────────

    async def _auto_warn(self, message: discord.Message, member: discord.Member, reason: str):
        guild = message.guild

        warning_id = add_warning(
            guild_id=guild.id,
            user_id=member.id,
            moderator_id=self.bot.user.id,
            reason=f"[AutoMod] {reason}",
        )
        total_warnings = count_warnings(guild_id=guild.id, user_id=member.id)

        logger.info(f"[AutoMod] WARN | {member} | Grund: {reason} | Total: {total_warnings}")

        # DM an User
        try:
            await member.send(
                f"⚠️ **Automatische Verwarnung auf {guild.name}**\n"
                f"**Grund:** {reason}\n"
                f"Bitte halte dich an die Serverregeln."
            )
        except discord.Forbidden:
            pass

        # Modlog
        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                "🤖 AutoMod Verwarnung",
                f"**User:** {member.mention} ({member.id})\n"
                f"**Grund:** {reason}\n"
                f"**Verwarnungen gesamt:** {total_warnings}",
                discord.Color.orange()
            )

        # Auto-Aktionen via gemeinsame Funktion
        await handle_auto_actions(
            bot=self.bot,
            guild=guild,
            moderator=guild.me,
            user=member,
            total_warnings=total_warnings,
            warning_id=warning_id,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoHandler(bot))