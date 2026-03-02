import discord
from discord.ext import commands
from utils.config import config
from utils.logger import logger


class RulesReaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rules_channel_id = config.channels.get("rules_channel", 0)
        self.rules_message_id = config.rules.get("message_id", 0)
        self.reaction_role_key = config.rules.get("reaction_role", "")

        if not all([self.rules_channel_id, self.rules_message_id, self.reaction_role_key]):
            logger.warning("[RulesReaction] Konfiguration unvollständig – Cog inaktiv.")
            return
        
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Nur ✅ auf der richtigen Nachricht im richtigen Channel
        if payload.message_id != self.rules_message_id:
            return
        if payload.channel_id != self.rules_channel_id:
            return
        if str(payload.emoji) != "✅":
            return
        if payload.member.bot:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        # Rolle aus config holen
        role_id = config.roles.get(self.reaction_role_key)
        if not role_id:
            logger.error(f"[RulesReaction] Rolle '{self.reaction_role_key}' nicht in config.yaml gefunden.")
            return

        role = guild.get_role(int(role_id))
        if role is None:
            logger.error(f"[RulesReaction] Rolle ID {role_id} nicht auf dem Server gefunden.")
            return

        member = payload.member

        # Rolle vergeben
        try:
            await member.add_roles(role, reason="Regeln akzeptiert ✅")
            logger.info(f"[RulesReaction] {member} hat Rolle '{role.name}' erhalten.")
        except discord.Forbidden:
            logger.error("[RulesReaction] Keine Berechtigung – 'Rollen verwalten' Permission prüfen.")
        except discord.HTTPException as e:
            logger.error(f"[RulesReaction] HTTP Fehler: {e}")

        # Reaction entfernen
        try:
            channel = guild.get_channel(self.rules_channel_id)
            message = await channel.fetch_message(self.rules_message_id)
            await message.remove_reaction(payload.emoji, member)
        except Exception as e:
            logger.warning(f"[RulesReaction] Reaction konnte nicht entfernt werden: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RulesReaction(bot))