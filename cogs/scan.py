from discord.ext import commands
import discord
from discord import app_commands
import asyncio
from db import update_last_scanned_id, get_last_scanned_id, archive_message, is_message_archived

class Scan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------- /scan ------------
    @app_commands.command(
        name="scan",
        description="Scanne un canal (1000 derniers messages par défaut) et archive."
    )
    @app_commands.describe(
        channel="Le canal à scanner",
        limit_per_channel="Nombre de messages maximum à scanner (par défaut 1000)"
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
            if message.author.bot:
                continue
            if is_message_archived(message.id):
                continue
            if not message.content or message.content.strip() == "":
                continue

            for reaction in message.reactions:
                if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
                    image_url = None
                    if message.attachments:
                        for attachment in message.attachments:
                            if attachment.content_type and attachment.content_type.startswith("image/"):
                                image_url = attachment.url
                                break

                    message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message.id}"

                    archive_message(
                        message.id,
                        message.content,
                        reaction.count,
                        channel.id,
                        interaction.guild.id,
                        message.author.name,
                        message_url,
                        image_url,
                        str(reaction.emoji)
                    )
                    total_archived += 1
                    break

            update_last_scanned_id(channel.id, message.id)

            counter += 1
            if counter % 500 == 0:
                await asyncio.sleep(2)  # pause anti-rate-limit

        await interaction.followup.send(f"✅ Scan terminé sur {channel.mention}, {total_archived} messages archivés.")

    # ----------- /scan_all ------------
    @app_commands.command(
        name="scan_all",
        description="Scanne tous les canaux texte du serveur."
    )
    @app_commands.describe(limit_per_channel="Nombre de messages maximum à scanner par canal (par défaut 1000)")
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
                    if message.author.bot:
                        continue
                    if is_message_archived(message.id):
                        continue
                    if not message.content or message.content.strip() == "":
                        continue

                    for reaction in message.reactions:
                        if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
                            image_url = None
                            if message.attachments:
                                for attachment in message.attachments:
                                    if attachment.content_type and attachment.content_type.startswith("image/"):
                                        image_url = attachment.url
                                        break
                            message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message.id}"

                            archive_message(
                                message.id,
                                message.content,
                                reaction.count,
                                channel.id,
                                interaction.guild.id,
                                message.author.name,
                                message_url,
                                image_url,
                                str(reaction.emoji)
                            )
                            total_archived += 1
                            break

                    update_last_scanned_id(channel.id, message.id)

                # optionnel : feedback canal par canal
                await interaction.followup.send(f"✅ Fin du scan de {channel.mention}.", ephemeral=True)

            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ Pas d’accès à {channel.mention}, ignoré.", ephemeral=True)

        await interaction.followup.send(f"🎉 Scan terminé. {total_archived} messages archivés au total.")

    # ----------- /scan_full ------------
    @app_commands.command(
        name="scan_full",
        description="Scanne un canal en entier (tous les messages)."
    )
    @app_commands.describe(channel="Le canal à scanner entièrement")
    async def scan_full(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(f"📜 Début du scan complet de {channel.mention}...", ephemeral=True)

        total_archived = 0
        scanned = 0
        last_message = None

        try:
            while True:
                messages = [m async for m in channel.history(limit=100, before=last_message)]
                if not messages:
                    break

                for message in messages:
                    scanned += 1
                    if message.author.bot:
                        continue
                    if is_message_archived(message.id):
                        continue
                    if not message.content or message.content.strip() == "":
                        continue

                    for reaction in message.reactions:
                        if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
                            image_url = None
                            if message.attachments:
                                for attachment in message.attachments:
                                    if attachment.content_type and attachment.content_type.startswith("image/"):
                                        image_url = attachment.url
                                        break

                            message_url = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{message.id}"

                            archive_message(
                                message.id,
                                message.content,
                                reaction.count,
                                channel.id,
                                interaction.guild.id,
                                message.author.name,
                                message_url,
                                image_url,
                                str(reaction.emoji)
                            )
                            total_archived += 1
                            break

                    last_message = message

                if scanned % 1000 == 0:
                    await asyncio.sleep(3)
                if scanned % 20000 == 0:
                    await interaction.followup.send(f"🔍 Scan en cours dans {channel.mention} : {scanned} messages scannés, {total_archived} archivés.", ephemeral=True)

            await interaction.followup.send(f"✅ Scan terminé dans {channel.mention} : {scanned} messages scannés, {total_archived} archivés.")

        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas accès à ce canal.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Erreur pendant le scan : {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Scan(bot))
