import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from db import DB_PATH

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="stats",
        description="Affiche des statistiques sur les messages archivés."
    )
    async def stats(self, interaction: discord.Interaction):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Nombre total de messages archivés
        cursor.execute("SELECT COUNT(*) FROM archived_messages")
        total_archived = cursor.fetchone()[0] or 0

        # Top 10 auteurs
        cursor.execute(
            "SELECT author_name, COUNT(*) as count FROM archived_messages "
            "GROUP BY author_name ORDER BY count DESC LIMIT 10"
        )
        top_authors = cursor.fetchall()

        # Top 10 emojis
        cursor.execute(
            "SELECT reaction_emoji, COUNT(*) as count FROM archived_messages "
            "WHERE reaction_emoji IS NOT NULL "
            "GROUP BY reaction_emoji ORDER BY count DESC LIMIT 10"
        )
        top_emojis = cursor.fetchall()

        conn.close()

        # Embed
        embed = discord.Embed(
            title="📊 Statistiques des archives",
            description=f"**Total des messages archivés : {total_archived}**",
            color=discord.Color.blue()
        )

        if top_authors:
            authors_text = "\n".join([f"**{i+1}. {name}** — {count} messages"
                                     for i, (name, count) in enumerate(top_authors)])
            embed.add_field(name="🏆 Auteurs les plus archivés", value=authors_text, inline=False)
        else:
            embed.add_field(name="🏆 Auteurs les plus archivés", value="Aucune donnée.", inline=False)

        if top_emojis:
            emojis_text = "\n".join([f"**{i+1}. {emoji}** — {count} utilisations"
                                    for i, (emoji, count) in enumerate(top_emojis)])
            embed.add_field(name="😀 Emojis les plus utilisés", value=emojis_text, inline=False)
        else:
            embed.add_field(name="😀 Emojis les plus utilisés", value="Aucune donnée.", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Stats(bot))
