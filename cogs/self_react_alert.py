import discord
from discord.ext import commands
import random
import time

class SelfReactAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dictionnaire pour gérer le cooldown par utilisateur : {user_id: timestamp}
        self.last_triggered = {}

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Ignorer les bots
        if user.bot:
            return

        message = reaction.message

        # Vérifie si l'utilisateur réagit à son propre message
        if message.author.id != user.id:
            return

        # Cooldown de 60 secondes par utilisateur
        now = time.time()
        last_time = self.last_triggered.get(user.id, 0)
        if now - last_time < 60:
            return  # Trop tôt, on ignore

        # Met à jour le dernier déclenchement
        self.last_triggered[user.id] = now

        # Liste de messages rigolos
        funny_messages = [
            f"😏 {user.mention} se suce allègrement, on a l'habitude...",
            f"😂 {user.mention} est prêt à tout pour stonks ses stats, sachez-le.",
            f"🤡 {user.mention}, poti clown on l'a vu ta react tu croyais quoi ?",
            f"{user.mention} est prêt à tout pour rattraper Olivier (sauf si c'est Olivier qui s'est auto-react j'ai la flemme de coder le bot pour faire la différence bref).",
            f"📸 {user.mention} attrapé en 4k pour self-react",
            f"🚨 {user.mention}, ceci est une descente de police haha j'ai dead ça la team ou quoi",
        ]

        response = random.choice(funny_messages)

        # Envoi du message (silencieusement si pas les permissions)
        try:
            await message.channel.send(response)
        except discord.Forbidden:
            pass

async def setup(bot):
    await bot.add_cog(SelfReactAlert(bot))
