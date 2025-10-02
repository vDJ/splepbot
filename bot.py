import discord
from discord.ext import commands

intents = discord.Intents.all()

# Crée une instance du bot avec un préfixe de commande (par exemple "!")
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot connecté en tant que {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

# Remplace 'YOUR_TOKEN' par ton token de bot
bot.run('MTQyMzIyMTU2MjQ2MjQzNzM5Ng.GPVwdn.71dlmYUjDRnLkrWzRYWVIQ8w_E11VlZlUjNJQQ')