import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ============================
# CONFIGURATION DU BOT
# ============================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Extensions / cogs à charger
initial_extensions = [
    "cogs.general",
    "cogs.archive",
    "cogs.scan",
    "cogs.polls",
    "cogs.config"
]

# ============================
# ÉVÉNEMENT ON_READY
# ============================

@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    # Synchronisation des slash commands
    await bot.tree.sync()
    print("🌐 Slash commands synchronisées.")

# ============================
# LANCEMENT DU BOT
# ============================

async def main():
    # Charger les cogs avant de démarrer le bot
    for ext in initial_extensions:
        try:
            await bot.load_extension(ext)
            print(f"📦 Extension chargée : {ext}")
        except Exception as e:
            print(f"⚠️ Impossible de charger {ext}: {e}")

    # Lancer le bot
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
