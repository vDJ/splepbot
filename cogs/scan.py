from discord.ext import commands
import discord
from discord import app_commands
import asyncio
from db import update_last_scanned_id, get_last_scanned_id, is_message_archived
from cogs.archive import try_archive_message  # On réutilise la fonction commune

class Scan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------- /scan ------------
    @app_commands.command(
        name="scan",
        description="Scanne un canal (1000 derniers messages par défaut) et archive."
    )
    async def scan(self, interaction: discord.Interaction, channel: discord.TextChannel, limit_per_channel: int = 1000):
        await interaction.response.send_message(f"🔍 Scan du canal {channel.mention} en cours...", ephemeral=True)

        total_archived = 0
        last_id = get_last_scanned_id(channel.id)
        history_args = {'limit': limit_per_channel}
        if last_id:
            history_args['after'] = discord.Object(id=last_id)

        counter = 0
        async for message in channel.history(**history_args):
            if await try_archive_message(self.bot, message):
                total_archived += 1
            update_last_scanned_id(channel.id, message.id)

            counter += 1
            if counter % 500 == 0:
                await asyncio.sleep(2)

        await interaction.followup.send(f"✅ Scan terminé sur {channel.mention}, {total_archived} messages archivés.")

    # ----------- /scan_all ------------
    @app_commands.command(
        name="scan_all",
        description="Scanne tous les canaux texte du serveur."
    )
    async def scan_all(self, interaction: discord.Interaction, limit_per_channel: int = 1000):
        await interaction.response.send_message("🔍 Scan de tous les salons texte en cours...", ephemeral=True)

        total_archived = 0
        for channel in interaction.guild.text_channels:
            try:
                last_id = get_last_scanned_id(channel.id)
                history_args = {'limit': limit_per_channel}
                if last_id:
                    history_args['after'] = discord.Object(id=last_id)

                async for message in channel.history(**history_args):
                    if await try_archive_message(self.bot, message):
                        total_archived += 1
                    update_last_scanned_id(channel.id, message.id)

                await interaction.followup.send(f"✅ Fin du scan de {channel.mention}.", ephemeral=True)

            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ Pas d’accès à {channel.mention}, ignoré.", ephemeral=True)

        await interaction.followup.send(f"🎉 Scan terminé. {total_archived} messages archivés au total.")

    # ----------- /scan_full ------------
    @app_commands.command(
        name="scan_full",
        description="Scanne un canal en entier (tous les messages)."
    )
    async def scan_full(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(f"📜 Début du scan complet de {channel.mention}...", ephemeral=True)

        total_archived = 0
        scanned = 0
        empty_batches = 0

        last_scanned_id = get_last_scanned_id(channel.id)
        last_message = discord.Object(id=last_scanned_id) if last_scanned_id else None

        try:
            while True:
                messages = [m async for m in channel.history(limit=100, before=last_message)]

                print(f"[DEBUG] Fetched {len(messages)} messages "
                    f"(before={last_message.id if last_message else None}, "
                    f"scanned={scanned}, archived={total_archived})")

                if not messages:
                    empty_batches += 1
                    print(f"[DEBUG] Batch vide #{empty_batches} (last_message={last_message.id if last_message else None})")

                    if empty_batches >= 3:
                        print("[DEBUG] 3 batchs vides consécutifs → fin du scan")
                        break

                    await asyncio.sleep(5)
                    continue

                empty_batches = 0

                for message in messages:
                    scanned += 1
                    if await try_archive_message(self.bot, message):
                        total_archived += 1
                        print(f"[ARCHIVE] ✅ Message {message.id} archivé (auteur={message.author})")

                    last_message = message

                    if scanned % 500 == 0:
                        update_last_scanned_id(channel.id, last_message.id)

                if scanned % 1000 == 0:
                    await asyncio.sleep(3)
                if scanned % 20000 == 0:
                    await interaction.followup.send(
                        f"🔍 Scan en cours dans {channel.mention} : "
                        f"{scanned} messages scannés, {total_archived} archivés.",
                        ephemeral=True
                    )

            if last_message:
                update_last_scanned_id(channel.id, last_message.id)

            await interaction.followup.send(
                f"✅ Scan terminé dans {channel.mention} : {scanned} messages scannés, {total_archived} archivés."
            )

        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas accès à ce canal.", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] Exception during scan_full: {e}")
            await interaction.followup.send(f"⚠️ Erreur pendant le scan : {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Scan(bot))
