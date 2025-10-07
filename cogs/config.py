from discord.ext import commands

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def set_threshold(self, ctx, new_threshold: int):
        """Modifie dynamiquement le seuil de réactions nécessaire à l’archivage."""
        self.bot.reaction_threshold = new_threshold
        await ctx.send(f"🔧 Le seuil des réactions est maintenant de {new_threshold}.")

    # Ici tu pourras ajouter d'autres commandes de configuration
    # Exemple : set_prefix, toggle_feature, etc.

async def setup(bot):
    await bot.add_cog(Config(bot))
