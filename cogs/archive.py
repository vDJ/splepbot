from discord.ext import commands
import discord
import sqlite3
from db import archive_message, is_message_archived, get_archived_message, DB_PATH

class Archive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def archive(self, ctx, message_id: int = None):
        """
        Archive un message :
        - si message_id donné, archive ce message,
        - sinon archive le message auquel la commande répond (reply).
        """
        target_message = None

        if message_id:
            try:
                target_message = await ctx.channel.fetch_message(message_id)
            except discord.NotFound:
                await ctx.send("⚠️ Message introuvable avec cet ID.")
                return
        else:
            if ctx.message.reference is None:
                await ctx.send("⚠️ Tu dois soit donner un ID, soit répondre à un message pour l’archiver.")
                return
            try:
                target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            except discord.NotFound:
                await ctx.send("⚠️ Message référencé introuvable.")
                return

        if target_message.author.bot:
            await ctx.send("⚠️ Impossible d’archiver un message posté par un bot.")
            return

        if is_message_archived(target_message.id):
            await ctx.send("⚠️ Ce message est déjà archivé.")
            return

        if not target_message.content or target_message.content.strip() == "":
            await ctx.send("⚠️ Ce message ne contient pas de texte, il ne sera pas archivé.")
            return

        # Gérer l'image éventuelle
        image_url = None
        if target_message.attachments:
            for attachment in target_message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    image_url = attachment.url
                    break

        # Lien vers le message
        url = f"https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id}"

        # Nombre maximum de réactions
        max_reactions = max([r.count for r in target_message.reactions], default=0)
        reaction_emoji = str(target_message.reactions[0].emoji) if target_message.reactions else None

        # Archiver le message
        archive_message(
            target_message.id,
            target_message.content,
            max_reactions,
            target_message.channel.id,
            target_message.guild.id,
            target_message.author.name,
            url,
            image_url,
            reaction_emoji
        )

        await ctx.send(f"💾 Message archivé avec succès : {target_message.content[:50]}...\nLien : {url}")

    @commands.command()
    async def show_message(self, ctx, message_id: int):
        """Affiche anonymement un message archivé (par son ID)."""
        content = get_archived_message(message_id)
        if content:
            content_anonymized = content[:200]
            await ctx.send(f"📄 **Message anonymisé :**\n{content_anonymized}")
        else:
            await ctx.send("⚠️ Message non trouvé dans la base.")

    @commands.command()
    async def random_message(self, ctx):
        """Affiche un message archivé aléatoire anonymisé avec lien."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT message_id, content, message_url, image_url, reaction_emoji FROM archived_messages ORDER BY RANDOM() LIMIT 1')
        result = cursor.fetchone()
        conn.close()

        if result:
            message_id, content, url, image_url, reaction_emoji = result
            content_anonymized = content[:200]

            embed = discord.Embed(
                title="🎲 Message aléatoire",
                description=content_anonymized,
                color=discord.Color.blurple()
            )
            if reaction_emoji:
                embed.add_field(name="Réaction", value=reaction_emoji, inline=True)

            embed.add_field(name="Lien", value=f"[Voir sur Discord]({url})", inline=False)

            if image_url:
                embed.set_image(url=image_url)

            await ctx.send(embed=embed)
        else:
            await ctx.send("⚠️ Aucun message archivé pour le moment.")


    # Quand une réaction est ajoutée
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return  # Ignore les réactions des bots

        message = reaction.message
        if message.author.bot:
            return  # Ignore les messages postés par des bots
        
        if not message.content or message.content.strip() == "":
            return  # Ignore messages sans texte


        # Si le message atteint le seuil de réactions
        if reaction.count >= getattr(self.bot, "reaction_threshold", 4):
            if not is_message_archived(message.id):
                # À placer juste avant l'appel à archive_message
                image_url = None
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith("image/"):
                            image_url = attachment.url
                            break

                archive_message(
                    message.id,
                    message.content,
                    reaction.count,
                    message.channel.id,
                    message.guild.id,
                    message.author.name,
                    f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}", 
                    image_url,
                    str(reaction.emoji)
                )
                await message.channel.send(f"💾 Message archivé (seuil atteint) : {message.content[:50]}...")

    


async def setup(bot):
    await bot.add_cog(Archive(bot))
