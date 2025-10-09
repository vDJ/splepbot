import discord
from discord.ext import commands
from discord import app_commands
from db import get_random_archived_message, get_archived_message

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Test basique pour vérifier si le bot répond."""
        await ctx.send("Pong !")

    # ----------- /random_archived ------------
    @app_commands.command(
        name="random_archived",
        description="Affiche un message archivé aléatoire."
    )
    async def random_archived(self, interaction: discord.Interaction):
        row = get_random_archived_message()
        if not row:
            await interaction.response.send_message("⚠️ Aucun message archivé disponible.", ephemeral=True)
            return
        
        message_id, content, author_name, message_url, image_url, reaction_emoji = row

        embed = discord.Embed(
            title=f"🗂️ Message archivé (ID {message_id})",
            description=(content[:1000] + "..." if content and len(content) > 1000 else content) or "*[Sans contenu]*",
            color=discord.Color.blue()
        )
        embed.add_field(name="Auteur", value=author_name, inline=True)
        embed.add_field(name="Lien", value=f"[Aller au message original]({message_url})", inline=True)
        if image_url:
            embed.set_image(url=image_url)
        if reaction_emoji:
            embed.add_field(name="Réaction", value=reaction_emoji, inline=True)

        await interaction.response.send_message(embed=embed)


    # ----------- /show_message_by_id ------------
    @app_commands.command(
        name="show_message_by_id",
        description="Affiche un message archivé à partir de son ID."
    )
    async def show_message_by_id(self, interaction: discord.Interaction, message_id: str):
        row = get_archived_message(message_id)
        if not row:
            await interaction.response.send_message("⚠️ Aucun message archivé avec cet ID.", ephemeral=True)
            return
        
        message_id, content, author_name, message_url, image_url, reaction_emoji = row

        embed = discord.Embed(
            title=f"🗂️ Message archivé (ID {message_id})",
            description=(content[:1000] + "..." if content and len(content) > 1000 else content) or "*[Sans contenu]*",
            color=discord.Color.green()
        )
        embed.add_field(name="Auteur", value=author_name, inline=True)
        embed.add_field(name="Lien", value=f"[Aller au message original]({message_url})", inline=True)
        if image_url:
            embed.set_image(url=image_url)
        if reaction_emoji:
            embed.add_field(name="Réaction", value=reaction_emoji, inline=True)

        await interaction.response.send_message(embed=embed)


# Cette fonction est nécessaire pour que load_extension fonctionne
async def setup(bot):
    await bot.add_cog(General(bot))
# Elle permet de charger le cog dans le bot