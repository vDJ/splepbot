import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
import random
import sqlite3
from db import DB_PATH

# ============================
# VIEW POUR LE VOTE
# ============================

class VotingView(View):
    def __init__(self, choices, true_author, message_url, image_url=None, reaction_emoji=None, timeout=30):
        super().__init__(timeout=timeout) #timeout personnalisable, défaut 30s
        self.timeout_value = timeout
        self.votes = {choice: 0 for choice in choices}
        self.voted_users = {}  # user_id -> choix
        self.true_author = true_author
        self.message_url = message_url
        self.image_url = image_url
        self.reaction_emoji = reaction_emoji
        self.message = None  # sera assigné après l’envoi du message

        for choice in choices:
            button = Button(label=choice, style=discord.ButtonStyle.primary)
            button.callback = self.make_callback(choice)
            self.add_item(button)

    def make_callback(self, choice):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.voted_users:
                await interaction.response.send_message("❌ Tu as déjà voté.", ephemeral=True)
                return
            self.votes[choice] += 1
            self.voted_users[interaction.user.id] = choice
            await interaction.response.send_message(f"✅ Vote reçu pour **{choice}**.", ephemeral=True)
        return callback

    async def on_timeout(self):
        if self.message is None:
            return  # sécurité

        # Résultats des votes
        results_text = "\n".join(f"**{choice}** : {count} vote(s)" for choice, count in self.votes.items())
        winners_ids = [uid for uid, vote in self.voted_users.items() if vote == self.true_author]
        winners_message = (
            "🎉 Félicitations aux bons devineurs : " + " ".join(f"<@{uid}>" for uid in winners_ids)
            if winners_ids else "Aucun bon vote cette fois, essayez encore !"
        )

        # Désactiver les boutons
        for item in self.children:
            item.disabled = True

        # Message final
        final_msg = (
            f"📊 Résultats du sondage (⏳ {self.timeout_value}s) :\n{results_text}\n\n"
            f"✅ La bonne réponse était : **{self.true_author}**\n"
            f"🔗 [Lien vers le message original]({self.message_url})\n\n"
            f"{winners_message}"
        )

        await self.message.edit(content=final_msg, view=self)

# ============================
# COMMANDE POUR LES POLLS
# ============================

class Polls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="random_message_poll",
        description="Affiche un message archivé anonymisé avec vote pour l’auteur."
    )
    async def random_message_poll(self, interaction: discord.Interaction, timeout : int = 30):
#         Lancement d'un sondage avec un message archivé.
#         :param timeout: durée du sondage en secondes (par défaut 30s).

        if timeout < 15 or timeout > 1800:
            await interaction.response.send_message("⚠️ Le temps doit être entre 15 et 1800 secondes.", ephemeral=True)
            return
        
        # Connexion à la base
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT message_id, content, author_name, message_url, image_url, reaction_emoji '
            'FROM archived_messages' 
            'ORDER BY times_polled ASC, RANDOM() LIMIT 1'
        )
        row = cursor.fetchone()
        if not row:
            await interaction.response.send_message("⚠️ Aucun message archivé pour le moment.")
            conn.close()
            return
        
        message_id, content, true_author, message_url, image_url, reaction_emoji = row

        cursor.execute(
            'SELECT DISTINCT author_name FROM archived_messages WHERE author_name != ? ORDER BY RANDOM() LIMIT 2',
            (true_author,)
        )
        other_authors = [r[0] for r in cursor.fetchall()]

        # incrémenter le compteur
        cursor.execute("UPDATE archived_messages SET times_polled = times_polled + 1 WHERE message_id = ?", (message_id,))
        conn.commit()

        conn.close()

        choices = [true_author] + other_authors
        random.shuffle(choices)
        content_anonymized = content[:1000] + ("..." if len(content) > 1000 else "")

        # Si c’est un tweet → on l’affiche directement
        if content and ("twitter.com" in content or "x.com" in content):
            await interaction.response.send_message(content)
            return

        # Sinon embed normal
        embed = discord.Embed(
            title="📄 Devine l’auteur du message anonymisé",
            description=content_anonymized,
            color=discord.Color.orange()
        )
        if image_url:
            embed.set_image(url=image_url)
        if reaction_emoji:
            embed.add_field(name="Réaction", value=reaction_emoji, inline=True)

        # Déclarer la view
        voting_view = VotingView(choices, true_author, message_url, image_url= image_url, reaction_emoji=reaction_emoji, timeout=timeout)

        # Déférer la réponse et envoyer le message
        await interaction.response.defer()
        message = await interaction.followup.send(embed=embed, view=voting_view)
        voting_view.message = message

# ============================
# SETUP DU COG
# ============================

async def setup(bot):
    await bot.add_cog(Polls(bot))
