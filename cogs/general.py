from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Test basique pour vérifier si le bot répond."""
        await ctx.send("Pong !")

# Cette fonction est nécessaire pour que load_extension fonctionne
async def setup(bot):
    await bot.add_cog(General(bot))
# Elle permet de charger le cog dans le bot