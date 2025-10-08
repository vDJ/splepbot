from discord.ext import commands
import discord
from discord import app_commands
import sqlite3
from db import archive_message, is_message_archived, get_archived_message, DB_PATH

# ============================
# FONCTION UTILITAIRE
# ============================
async def try_archive_message(bot, target_message: discord.Message) -> bool:
    """Tente d’archiver un message. Retourne True si succès, False sinon."""
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

    # Vérifier le seuil minimal
    if max_reactions < getattr(bot, "reaction_threshold", 4):
        return False

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

    # --- LOG CONSOLE ---
    print(f"[ARCHIVE] ✅ Message {target_message.id} archivé "
          f"(auteur={target_message.author}, réactions={max_reactions}, canal={target_message.channel})")

    return True


# ============================
# COG ARCHIVE
# ============================
class Archive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- SLASH COMMAND ---
    @app_commands.command(
        name="archive",
        description="Archive un message par son ID."
    )
    @app_commands.describe(message_id="L'ID du message à archiver")
    async def archive(self, interaction: discord.Interaction, message_id: str):
        try:
            target_message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message("⚠️ Message introuvable avec cet ID.", ephemeral=True)
            return

        if await try_archive_message(self.bot, target_message):
            await interaction.response.send_message(
                f"💾 Message archivé avec succès : {target_message.content[:200]}...\n"
                f"[Voir le message](https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id})"
            )
        else:
            await interaction.response.send_message("⚠️ Ce message n’a pas pu être archivé.", ephemeral=True)

    # --- PREFIX COMMAND ---
    @commands.command(name="archive")
    async def archive_prefix(self, ctx):
        if not ctx.message.reference:
            await ctx.send("⚠️ Tu dois répondre à un message pour l’archiver avec `!archive`.")
            return

        try:
            target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            await ctx.send("⚠️ Message introuvable.")
            return

        if await try_archive_message(self.bot, target_message):
            await ctx.send(
                f"💾 Message archivé avec succès : {target_message.content[:50]}...\n"
                f"[Voir le message](https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id})"
            )
        else:
            await ctx.send("⚠️ Ce message n’a pas pu être archivé.")

    # --- UNARCHIVE ---
    @app_commands.command(
        name="unarchive",
        description="Désarchive un message (le supprime de la base)."
    )
    @app_commands.describe(message_id="L’ID du message à désarchiver")
    async def unarchive(self, interaction: discord.Interaction, message_id: str):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM archived_messages WHERE message_id = ?", (message_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            await interaction.response.send_message("⚠️ Ce message n’est pas archivé.", ephemeral=True)
            return

        cursor.execute("DELETE FROM archived_messages WHERE message_id = ?", (message_id,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"🗑️ Message {message_id} désarchivé avec succès.", ephemeral=True)

    # --- LISTENER ---
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        message = reaction.message
        if message.author.bot:
            return
        if not message.content or message.content.strip() == "":
            return

        if await try_archive_message(self.bot, message):
            await message.channel.send(f"💾 Message archivé (seuil atteint) : {message.content[:50]}...")

async def setup(bot):
    await bot.add_cog(Archive(bot))
