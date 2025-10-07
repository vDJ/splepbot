from discord.ext import commands
from discord.ui import Button, View
import discord
import random
import sqlite3
from db import DB_PATH

class VotingView(View):
    def __init__(self, choices, true_author, message_url, image_url=None, reaction_emoji=None):
        super().__init__(timeout=30)
        self.votes = {choice: 0 for choice in choices}
        self.voted_users = {}  # user_id -> choix
        self.true_author = true_author
        self.message_url = message_url
        self.image_url = image_url
        self.reaction_emoji = reaction_emoji

        for choice in choices:
            button = Button(label=choice, style=discord.ButtonStyle.primary)
            button.callback = self.make_callback(choice)
            self.add_item(button)

    def make_callback(self, choice):
        async def callback(interaction):
            if interaction.user.id in self.voted_users:
                await interaction.response.send_message("❌ Tu as déjà voté.", ephemeral=True)
                return
            self.votes[choice] += 1
            self.voted_users[interaction.user.id] = choice
            await interaction.response.send_message(f"✅ Vote reçu pour **{choice}**.", ephemeral=True)
        return callback

    async def on_timeout(self):
        # Résultats votes
        results_text = "\n".join(f"**{choice}** : {count} vote(s)" for choice, count in self.votes.items())

        # Gagnants qui ont voté juste
        winners_ids = [uid for uid, vote in self.voted_users.items() if vote == self.true_author]
        if winners_ids:
            winners_mentions = " ".join(f"<@{uid}>" for uid in winners_ids)
            winners_message = f"🎉 Félicitations aux bons devineurs : {winners_mentions} !"
        else:
            winners_message = "Aucun bon vote cette fois, essayez encore !"

        # Désactivation boutons
        for item in self.children:
            item.disabled = True

        # Affichage message final avec bonne réponse + lien
        final_msg = (
            f"📊 Résultats du sondage pour ce message :\n{results_text}\n\n"
            f"✅ La bonne réponse était : **{self.true_author}**\n"
            f"🔗 [Lien vers le message original]({self.message_url})\n\n"
            f"{winners_message}"
        )

        await self.message.edit(content=final_msg, view=self)

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="random_message_poll", description="Affiche un message archivé anonymisé avec vote pour l’auteur.")
    async def random_message_poll(self, interaction: discord.Interaction):
        """Affiche un message archivé anonymisé avec vote pour l’auteur."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Choisir un message aléatoire
        cursor.execute('SELECT message_id, content, author_name, message_url, image_url, reaction_emoji FROM archived_messages ORDER BY RANDOM() LIMIT 1')
        row = cursor.fetchone()
        if not row:
            await interaction.response.send_message("⚠️ Aucun message archivé pour le moment.")
            conn.close()
            return
        message_id, content, true_author, message_url, image_url, reaction_emoji = row

        # Choisir deux auteurs aléatoires pour le sondage
        cursor.execute('SELECT DISTINCT author_name FROM archived_messages WHERE author_name != ? ORDER BY RANDOM() LIMIT 2', (true_author,))
        other_authors = [r[0] for r in cursor.fetchall()]
        conn.close()

        choices = [true_author] + other_authors
        random.shuffle(choices)
        content_anonymized = content[:200] + ("..." if len(content) > 200 else "")

        embed = discord.Embed(
            title="📄 Devine l’auteur du message anonymisé",
            description=content_anonymized,
            color=discord.Color.orange()
        )

        if image_url:
            embed.set_image(url=image_url)

        if reaction_emoji:
            embed.add_field(name="Réaction", value=reaction_emoji, inline=True)

        voting_view = VotingView(choices, true_author, message_url)
        message = await interaction.response.send_message(embed=embed, view=voting_view)
        voting_view.message = message

async def setup(bot):
    await bot.add_cog(Polls(bot))
