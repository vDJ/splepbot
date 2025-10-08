import discord
from discord.ext import commands
from discord import app_commands
from db import get_leaderboard, get_user_points, reset_leaderboard

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ----------- /leaderboard ------------
    @app_commands.command(
        name="leaderboard",
        description="Affiche le classement des utilisateurs aux polls."
    )
    async def leaderboard(self, interaction: discord.Interaction):
        rows = get_leaderboard(limit=10)
        if not rows:
            await interaction.response.send_message("⚠️ Aucun score enregistré pour le moment.")
            return

        embed = discord.Embed(
            title="🏅 Classement des polls",
            color=discord.Color.gold()
        )

        lines = []
        for i, (user_id, points) in enumerate(rows, start=1):
            lines.append(f"**{i}. <@{user_id}>** — {points} point(s)")

        embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed)

    # ----------- /mypoints ------------
    @app_commands.command(
        name="mypoints",
        description="Affiche ton nombre de points obtenus dans les sondages."
    )
    async def mypoints(self, interaction: discord.Interaction):
        points = get_user_points(interaction.user.id)
        await interaction.response.send_message(
            f"🏅 Tu as actuellement **{points}** points, {interaction.user.mention} !",
            ephemeral=True
        )

    # ----------- /reset_leaderboard ------------
    @app_commands.command(
        name="reset_leaderboard",
        description="Réinitialise tous les scores (admin uniquement)."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_leaderboard_cmd(self, interaction: discord.Interaction):
        reset_leaderboard()
        await interaction.response.send_message("♻️ Le leaderboard a été réinitialisé avec succès !")

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
