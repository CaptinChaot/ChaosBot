# cogs/tickets.py

import discord
from discord.ext import commands
from discord import app_commands

from utils.config import config
from utils.tickets.views import TicketPanelView, TicketChannelView
from utils.tickets.manager import create_ticket_channel, claim_ticket, archive_ticket
from utils.permissions import get_user_perm_level, PermLevel


GUILD = discord.Object(id=config.guild_id)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Persistent Views werden nur registriert, wenn Feature aktiv ist
        if config.features.get("tickets", False):
            self.bot.add_view(TicketPanelView())
            self.bot.add_view(TicketChannelView())
            print("Tickets: Persistent Views registriert")
        else:
            print("Tickets: Persistent Views NICHT registriert – Feature deaktiviert")

    # ==================================================
    # /send_ticket_panel (DEV+)
    # ==================================================

    @app_commands.command(
        name="send_ticket_panel",
        description="Sendet das Ticket-Panel (DEV/OWNER only)"
    )
    @app_commands.guilds(GUILD)
    async def send_ticket_panel(self, interaction: discord.Interaction):
        if not config.features.get("tickets", False):
            await interaction.response.send_message(
                "Ticket-System ist aktuell deaktiviert.",
                ephemeral=True
            )
            return

        if get_user_perm_level(interaction.user) < PermLevel.DEV:
            await interaction.response.send_message(
                "❌ Dafür hast du keine Berechtigung.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 Ticketsystem",
            description=(
                "Bitte wähle aus, **wobei wir dir helfen können**.\n\n"
                "➡️ Wähle eine Kategorie\n"
                "➡️ Beschreibe dein Problem\n"
                "➡️ Ein privater Ticket-Channel wird erstellt"
            ),
            color=discord.Color.blurple()
        )

        await interaction.channel.send(
            embed=embed,
            view=TicketPanelView()
        )

        await interaction.response.send_message(
            "✅ Ticket-Panel wurde gesendet.",
            ephemeral=True
        )

    # ==================================================
    # /sync_tickets (OWNER)
    # ==================================================

    @app_commands.command(
        name="sync_tickets",
        description="Synchronisiert Ticket Slash Commands (OWNER)"
    )
    @app_commands.guilds(GUILD)
    async def sync_tickets(self, interaction: discord.Interaction):
        if not config.features.get("tickets", False):
            await interaction.response.send_message(
                "Ticket-System ist aktuell deaktiviert.",
                ephemeral=True
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ Nur der Server-Owner.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        synced = await self.bot.tree.sync(guild=interaction.guild)

        await interaction.followup.send(
            f"✅ {len(synced)} Ticket-Slash-Commands synchronisiert.",
            ephemeral=True
        )

    # ==================================================
    # EVENT: Ticket aus Modal (views.py → dispatch)
    # ==================================================

    @commands.Cog.listener()
    async def on_ticket_submit(self, interaction: discord.Interaction, data: dict):
        if not config.features.get("tickets", False):
            await interaction.followup.send(
                "Ticket-System ist aktuell deaktiviert – bitte später erneut versuchen.",
                ephemeral=True
            )
            return

        try:
            channel = await create_ticket_channel(
                bot=self.bot,
                guild=interaction.guild,
                user=interaction.user,
                ticket_type=data["type"],
                description=data["description"],
            )

            await channel.send(
                "Support kann das Ticket jetzt **claimen** oder **schließen**:",
                view=TicketChannelView()
            )

            await interaction.followup.send(
                f"✅ Dein Ticket wurde erstellt: {channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Ticket konnte nicht erstellt werden: {type(e).__name__}: {e}",
                ephemeral=True
            )

    # ==================================================
    # COMPONENTS: Claim / Close Buttons
    # ==================================================

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        if custom_id not in ("ticket_claim", "ticket_close"):
            return

        if not config.features.get("tickets", False):
            await interaction.response.send_message(
                "Ticket-System ist aktuell deaktiviert – Aktion nicht möglich.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if custom_id == "ticket_claim":
                await claim_ticket(
                    bot=self.bot,
                    channel=interaction.channel,
                    claimer=interaction.user
                )
                await interaction.followup.send(
                    "✅ Ticket wurde geclaimed.",
                    ephemeral=True
                )

            elif custom_id == "ticket_close":
                await archive_ticket(
                    bot=self.bot,
                    channel=interaction.channel,
                    closed_by=interaction.user
                )
                await interaction.followup.send(
                    "🗂 Ticket wurde archiviert.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Aktion fehlgeschlagen: {type(e).__name__}: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    # Cog nur laden, wenn Feature aktiv ist (zusätzlicher Schutz)
    if config.features.get("tickets", False):
        await bot.add_cog(Tickets(bot))
        print("Tickets-Cog geladen")
    else:
        print("Tickets-Cog NICHT geladen – Feature deaktiviert")