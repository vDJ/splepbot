from discord.ext import commands
import discord
import asyncio
from db import update_last_scanned_id, get_last_scanned_id, archive_message, is_message_archived, DB_PATH

class Scan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command() #scan un canal (1000 derniers messages ou 14 derniers jours, pas sûr)
    @commands.has_permissions(administrator=True)
    async def scan(self, ctx, channel: discord.TextChannel, limit_per_channel: int = 1000):
        """Scanne un seul canal pour archiver les messages ayant assez de réactions."""
        total_archived = 0
        await ctx.send(f"🔍 Scan du canal {channel.mention} en cours...")

        last_id = get_last_scanned_id(channel.id)
        history_args = {'limit': limit_per_channel}
        if last_id:
            history_args['after'] = discord.Object(id=last_id)

        counter = 0
        async for message in channel.history(**history_args):
            if message.author.bot:
                continue # Ignore messages bots/apps

            if is_message_archived(message.id):
                continue

            if not message.content or message.content.strip() == "":
                continue # Ignore messages sans texte

            for reaction in message.reactions: # À placer juste avant l'appel à archive_message
                if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
                    image_url = None
                    if message.attachments:
                        for attachment in message.attachments:
                            if attachment.content_type and attachment.content_type.startswith("image/"):
                                image_url = attachment.url
                                break

                    message_url = f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message.id}"

                    archive_message(
                        message.id,
                        message.content,
                        reaction.count,
                        channel.id,
                        ctx.guild.id,
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

        await ctx.send(f"✅ Scan terminé sur {channel.mention}, {total_archived} messages archivés.")

    @commands.command() #scan tous les canaux auxquels le bot a accès (1000 derniers messages ou 14 derniers jours, pas sûr)
    @commands.has_permissions(administrator=True)
    async def scan_all(self, ctx, limit_per_channel: int = 1000):
        """Scanne tous les salons texte pour archiver les messages ayant assez de réactions."""
        total_archived = 0
        await ctx.send("🔍 Scan de tous les salons texte en cours...")

        for channel in ctx.guild.text_channels:
            await ctx.send(f"▶️ Scan de #{channel.name}...")
            try:
                last_id = get_last_scanned_id(channel.id)
                history_args = {'limit': limit_per_channel}
                if last_id:
                    history_args['after'] = discord.Object(id=last_id)

                counter = 0
                async for message in channel.history(**history_args):
                    if message.author.bot:
                        continue # Ignore les messages de bots/apps
                    if is_message_archived(message.id):
                        continue # Ignore les messages déjà archivés
                    if not message.content or message.content.strip() == "":
                        continue # Ignore messages sans texte
                    for reaction in message.reactions:
                        if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
                            image_url = None
                            if message.attachments:
                                for attachment in message.attachments:
                                    if attachment.content_type and attachment.content_type.startswith("image/"):
                                        image_url = attachment.url
                                        break
                            message_url = f"https://discord.com/channels/{message.guild.id}/{channel.id}/{message.id}"
                            archive_message(
                                message.id,
                                message.content,
                                reaction.count,
                                message.channel.id,
                                message.guild.id,
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
                        await asyncio.sleep(2) # Pause anti-rate-limit
                await ctx.send(f"✅ Fin du scan de #{channel.name}.")
            except discord.Forbidden:
                await ctx.send(f"⚠️ Pas d’accès à #{channel.name}, ignoré.")

        await ctx.send(f"🎉 Scan terminé. {total_archived} messages archivés au total.")

    @commands.command() #scan TOUS les messages d'un canal (peut être long)
    @commands.has_permissions(administrator=True)
    async def scan_full(self, ctx, channel: discord.TextChannel):

        await ctx.send(f"📜 Début du scan complet du canal {channel.mention}...")

        total_archived = 0
        scanned = 0
        last_message = None

        try:
            while True:
                # On récupère 100 messages à partir du plus récent ou du message précédent
                messages = [m async for m in channel.history(limit=100, before=last_message)]
                if not messages:
                    break # plus de messages à traiter

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

                            message_url = f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message.id}"

                            archive_message(
                                message.id,
                                message.content,
                                reaction.count,
                                channel.id,
                                ctx.guild.id,
                                message.author.name,
                                message_url,
                                image_url,
                                str(reaction.emoji)
                            )
                            total_archived += 1
                            break
                    
                    # Pour permettre la pagination "before="
                    last_message = message

                # Pause tous les 1000 messages
                if scanned % 1000 == 0:
                    await ctx.send(f"⏳ {scanned} messages scannés, {total_archived} archivés...")
                    await asyncio.sleep(3)

            await ctx.send(f"✅ Scan terminé dans {channel.mention} : {scanned} messages scannés, {total_archived} archivés.")

        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas accès à ce canal.")
        except Exception as e:
            await ctx.send(f"⚠️ Erreur pendant le scan : {e}")

async def setup(bot):
    await bot.add_cog(Scan(bot))
# Elle permet de charger le cog dans le bot