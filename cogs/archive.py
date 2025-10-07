from discord.ext import commands
import discord
from discord import app_commands
import sqlite3
from db import archive_message, is_message_archived, get_archived_message, DB_PATH

class Archive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ###################
    #COMMANDS
    ###################

    #On sépare la commande Archive en deux : une en slash command, une en préfixe
    # --- SLASH COMMAND ---
    @app_commands.command(
        name="archive",
        description="Archive un message par son ID."
    )
    @app_commands.describe(message_id="L'ID du message à archiver")
    async def archive(self, interaction: discord.Interaction, message_id: str):
        """Archive un message via son ID (slash command)."""
        try:
            target_message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message("⚠️ Message introuvable avec cet ID.", ephemeral=True)
            return

        if await self._archive_message(target_message):
            await interaction.response.send_message(
                f"💾 Message archivé avec succès : {target_message.content[:50]}...\n"
                f"[Voir le message](https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id})"
            )
        else:
            await interaction.response.send_message("⚠️ Ce message n’a pas pu être archivé.", ephemeral=True)

    # --- PREFIX COMMAND ---
    @commands.command(name="archive")
    async def archive_prefix(self, ctx):
        """Archive un message via reply (préfixe)."""
        if not ctx.message.reference:
            await ctx.send("⚠️ Tu dois répondre à un message pour l’archiver avec `!archive`.")
            return

        try:
            target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            await ctx.send("⚠️ Message introuvable.")
            return

        if await self._archive_message(target_message):
            await ctx.send(
                f"💾 Message archivé avec succès : {target_message.content[:50]}...\n"
                f"[Voir le message](https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id})"
            )
        else:
            await ctx.send("⚠️ Ce message n’a pas pu être archivé.")

    # --- FACTORISATION ---
    async def _archive_message(self, target_message: discord.Message) -> bool:
        """Logique commune d’archivage (utilisée par les deux commandes)."""
        if target_message.author.bot:
            return False
        if is_message_archived(target_message.id):
            return False
        if not target_message.content or target_message.content.strip() == "":
            return False

        # Gérer l'image éventuelle
        image_url = None
        if target_message.attachments:
            for attachment in target_message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    image_url = attachment.url
                    break

        url = f"https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id}"
        max_reactions = max([r.count for r in target_message.reactions], default=0)
        reaction_emoji = str(target_message.reactions[0].emoji) if target_message.reactions else None

        #fonction d'archivage à proprement parler
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
        return True


    # SHOW MESSAGE
    @commands.command()
    async def show_message(self, ctx, message_id: int):
        """Affiche anonymement un message archivé (par son ID)."""
        content = get_archived_message(message_id)
        if content:
            content_anonymized = content[:200]
            await ctx.send(f"📄 **Message anonymisé :**\n{content_anonymized}")
        else:
            await ctx.send("⚠️ Message non trouvé dans la base.")

    #SHOW RANDOM MESSAGE
    @app_commands.command(
        name="random_message",
        description="Affiche un message archivé aléatoire anonymisé avec lien."
    )
    async def random_message(self, interaction: discord.Interaction):
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

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("⚠️ Aucun message archivé pour le moment.")

    #UNARCHIVE MESSAGE
    @app_commands.command(
        name="unarchive",
        description="Désarchive un message (le supprime de la base)."
    )
    @app_commands.describe(message_id="L’ID du message à désarchiver")
    async def unarchive(self, interaction: discord.Interaction, message_id: str):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Vérifier si le message est dans la base
        cursor.execute("SELECT 1 FROM archived_messages WHERE message_id = ?", (message_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            await interaction.response.send_message("⚠️ Ce message n’est pas archivé.", ephemeral=True)
            return

        # Supprimer l'entrée
        cursor.execute("DELETE FROM archived_messages WHERE message_id = ?", (message_id,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"🗑️ Message {message_id} désarchivé avec succès.", ephemeral=True)

    #########################
    #LISTENER
    #########################
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
