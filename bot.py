import discord
from discord.ext import commands
from discord.ui import Button, View
import sqlite3
import asyncio
import random

# ============================
# CONFIGURATION DU BOT
# ============================

# Initialisation des intents (tous activés pour permettre la lecture des messages, des réactions, etc.)
intents = discord.Intents.all()

# Création de l'instance du bot avec le préfixe '!'
bot = commands.Bot(command_prefix='!', intents=intents)

# Seuil par défaut de réactions pour l'archivage automatique
reaction_threshold = 5

# Chemin vers la base de données SQLite (sera montée dans Docker)
DB_PATH = 'data/messages.db'

# ============================
# BASE DE DONNÉES
# ============================

# Initialise la base si elle n'existe pas
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS archived_messages (
                        id INTEGER PRIMARY KEY,
                        message_id INTEGER UNIQUE,
                        content TEXT,
                        reactions INTEGER,
                        channel_id INTEGER,
                        server_id INTEGER,
                        author_name TEXT,
                        message_url TEXT,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_progress (
                        channel_id INTEGER PRIMARY KEY,
                        last_message_id INTEGER
                    )''')

    conn.commit()
    conn.close()

# Archive un message dans la base
def archive_message(message_id, content, reactions, channel_id, server_id, author_name, message_url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO archived_messages 
                      (message_id, content, reactions, channel_id, server_id, author_name, message_url)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (message_id, content, reactions, channel_id, server_id, author_name, message_url))
    conn.commit()
    conn.close()


# Vérifie si un message a déjà été archivé
def is_message_archived(message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM archived_messages WHERE message_id = ?', (message_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None



# Récupère le contenu d'un message archivé
def get_archived_message(message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM archived_messages WHERE message_id = ?', (message_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# Récupère un message aléatoire depuis la base
def get_random_archived_message():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT message_id, content FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    return result if result else None

# Met à jour la position du dernier message scanné dans un salon
def update_last_scanned_id(channel_id, last_message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('REPLACE INTO scan_progress (channel_id, last_message_id) VALUES (?, ?)',
                   (channel_id, last_message_id))
    conn.commit()
    conn.close()

# Récupère l'ID du dernier message scanné dans un salon
def get_last_scanned_id(channel_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT last_message_id FROM scan_progress WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ============================
# ÉVÉNEMENTS DU BOT
# ============================

# Quand le bot se connecte
@bot.event
async def on_ready():
    init_db()
    print(f'✅ Bot connecté en tant que {bot.user}')

# Quand une réaction est ajoutée
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return  # Ignore les réactions des bots

    message = reaction.message
    if message.author.bot:
        return  # Ignore les messages postés par des bots

    # Si le message atteint le seuil de réactions
    if reaction.count >= reaction_threshold:
        if not is_message_archived(message.id):
            archive_message(
                message.id,
                message.content,
                reaction.count,
                message.channel.id,
                message.guild.id,
                message.author.name,
                f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
            )
            await message.channel.send(f"💾 Message archivé (seuil atteint) : {message.content[:50]}...")


# ============================
# COMMANDES DU BOT
# ============================

@bot.command()
async def ping(ctx):
    """Test basique pour vérifier si le bot répond."""
    await ctx.send("Pong !")

@bot.command()
async def set_threshold(ctx, new_threshold: int):
    """Modifie dynamiquement le seuil de réactions nécessaire à l’archivage."""
    global reaction_threshold
    reaction_threshold = new_threshold
    await ctx.send(f"🔧 Le seuil des réactions est maintenant de {reaction_threshold}.")

@bot.command()
async def archive(ctx, message_id: int = None):
    """
    Archive un message :
    - si message_id donné, archive ce message,
    - sinon archive le message auquel la commande répond (reply).
    """
    target_message = None

    if message_id:
        try:
            target_message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.send("⚠️ Message introuvable avec cet ID.")
            return
    else:
        if ctx.message.reference is None:
            await ctx.send("⚠️ Tu dois soit donner un ID, soit répondre à un message pour l’archiver.")
            return
        try:
            target_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        except discord.NotFound:
            await ctx.send("⚠️ Message référencé introuvable.")
            return

    if target_message.author.bot:
        await ctx.send("⚠️ Impossible d’archiver un message posté par un bot.")
        return

    if is_message_archived(target_message.id):
        await ctx.send("⚠️ Ce message est déjà archivé.")
        return

    max_reactions = max([r.count for r in target_message.reactions], default=0)
    url = f"https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id}"
    archive_message(
        target_message.id,
        target_message.content,
        max_reactions,
        target_message.channel.id,
        target_message.guild.id,
        target_message.author.name,
        url
    )
    await ctx.send(f"💾 Message archivé avec succès : {target_message.content[:50]}...\nLien : {url}")

@bot.command()
async def show_message(ctx, message_id: int):
    """Affiche anonymement un message archivé (par son ID)."""
    content = get_archived_message(message_id)
    if content:
        content_anonymized = content[:200]
        await ctx.send(f"📄 **Message anonymisé :**\n{content_anonymized}")
    else:
        await ctx.send("⚠️ Message non trouvé dans la base.")

@bot.command()
async def random_message(ctx):
    """Affiche un message archivé aléatoire anonymisé avec lien."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT message_id, content, message_url FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()

    if result:
        message_id, content, url = result
        content_anonymized = content[:200]
        await ctx.send(f"🎲 **Message aléatoire :**\n{content_anonymized}\n\n🔗 [Lien vers le message]({url})")
    else:
        await ctx.send("⚠️ Aucun message archivé pour le moment.")

""" class PollView(View):
    def __init__(self, message_id, choices):
        super().__init__(timeout=30)  # durée du sondage en secondes
        self.message_id = message_id
        self.choices = choices
        self.votes = {name: 0 for name in choices}
        self.voted_users = set()

        for name in choices:
            self.add_item(Button(label=name, style=discord.ButtonStyle.primary))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Empêche le vote multiple par un même utilisateur
        if interaction.user.id in self.voted_users:
            await interaction.response.send_message("❌ Tu as déjà voté.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Vote", style=discord.ButtonStyle.primary)
    async def button_callback(self, interaction: discord.Interaction, button: Button):
        # Cette méthode sera redéfinie plus bas via on_click
        pass

    async def on_button_click(self, interaction: discord.Interaction):
        label = interaction.data['custom_id'] if 'custom_id' in interaction.data else interaction.data['component_type']
        # On va plutôt gérer via interaction.component.label
        choice = interaction.data['custom_id'] if 'custom_id' in interaction.data else None

    async def on_timeout(self):
        # À la fin du timeout, on édite le message pour afficher les résultats
        results = "\n".join(f"**{k}** : {v} vote(s)" for k,v in self.votes.items())
        for child in self.children:
            child.disabled = True
        await self.message.edit(content=f"📊 Résultats du sondage pour le message {self.message_id} :\n{results}", view=self) """


 # Création d'une View custom pour gérer le vote
class VotingView(View):
    def __init__(self, choices, true_author):
        super().__init__(timeout=30)
        self.votes = {choice: 0 for choice in choices}
        self.voted_users = {}  # dict user_id -> choix
        self.true_author = true_author

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
        # Affichage des résultats
        results_text = "\n".join(f"**{choice}** : {count} vote(s)" for choice, count in self.votes.items())

        # Trouver les gagnants (ceux qui ont voté pour le vrai auteur)
        winners_ids = [user_id for user_id, vote in self.voted_users.items() if vote == self.true_author]

        # Préparation du message des gagnants
        if winners_ids:
            winners_mentions = " ".join(f"<@{user_id}>" for user_id in winners_ids)
            winners_message = f"🎉 Félicitations aux bons devineurs : {winners_mentions} !"
        else:
            winners_message = "Aucun bon vote cette fois, essayez encore !"

        # Désactiver tous les boutons
        for item in self.children:
            item.disabled = True

        # Modifier le message original pour afficher résultats + gagnants
        await self.message.edit(content=f"📊 Résultats du sondage pour ce message :\n{results_text}\n\n{winners_message}", view=self)


@bot.command()
async def random_message_poll(ctx):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT message_id, content, author_name FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    message_row = cursor.fetchone()
    if not message_row:
        await ctx.send("⚠️ Aucun message archivé pour le moment.")
        conn.close()
        return
    message_id, content, true_author = message_row

    cursor.execute('SELECT DISTINCT author_name FROM archived_messages WHERE author_name != ? ORDER BY RANDOM() LIMIT 2', (true_author,))
    other_authors = [row[0] for row in cursor.fetchall()]
    conn.close()

    choices = [true_author] + other_authors
    random.shuffle(choices)
    content_anonymized = content[:200]

    voting_view = VotingView(choices, true_author)
    message = await ctx.send(f"📄 **Devine l’auteur du message anonymisé :**\n{content_anonymized}", view=voting_view)
    voting_view.message = message


@bot.command()
@commands.has_permissions(administrator=True)
async def scan(ctx, channel: discord.TextChannel, limit_per_channel: int = 1000):
    """
    Scanne un seul canal pour archiver les messages ayant assez de réactions.
    Usage: !scan #nom_du_canal [limite_messages]
    """
    total_archived = 0
    await ctx.send(f"🔍 Scan du canal {channel.mention} en cours...")

    last_id = get_last_scanned_id(channel.id)
    history_args = {'limit': limit_per_channel}
    if last_id:
        history_args['after'] = discord.Object(id=last_id)

    counter = 0
    async for message in channel.history(**history_args):
        if message.author.bot:
            continue  # Ignore messages bots/apps

        if is_message_archived(message.id):
            continue

        for reaction in message.reactions:
            if reaction.count >= reaction_threshold:
                archive_message(
                    message.id,
                    message.content,
                    reaction.count,
                    channel.id,
                    ctx.guild.id,
                    message.author.name,
                    f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message.id}"
                )
                total_archived += 1
                break

        update_last_scanned_id(channel.id, message.id)

        counter += 1
        if counter % 500 == 0:
            await asyncio.sleep(2)  # Pause anti rate-limit

    await ctx.send(f"✅ Scan terminé sur {channel.mention}, {total_archived} messages archivés.")


@bot.command()
@commands.has_permissions(administrator=True)
async def scan_all(ctx, limit_per_channel: int = 1000):
    """Scanne tous les salons texte pour archiver les messages ayant assez de réactions."""
    total_archived = 0
    await ctx.send("🔍 Scan de tous les salons texte en cours...")

    for channel in ctx.guild.text_channels:
        await ctx.send(f"▶️ Scan de #{channel.name}...")
        try:
            last_id = get_last_scanned_id(channel.id)
            history_args = {'limit': limit_per_channel}
            if last_id:
                history_args['after'] = discord.Object(id=last_id)

            counter = 0
            async for message in channel.history(**history_args):
                if message.author.bot:
                    continue  # Ignore les messages de bots/apps

                if is_message_archived(message.id):
                    continue

                for reaction in message.reactions:
                    if reaction.count >= reaction_threshold:
                        archive_message(
                            message.id,
                            message.content,
                            reaction.count,
                            message.channel.id,
                            message.guild.id,
                            message.author.name,
                            f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                        )
                        total_archived += 1
                        break

                update_last_scanned_id(channel.id, message.id)

                counter += 1
                if counter % 500 == 0:
                    await asyncio.sleep(2)  # Pause anti-rate-limit
            await ctx.send(f"✅ Fin du scan de #{channel.name}.")
        except discord.Forbidden:
            await ctx.send(f"⚠️ Pas d’accès à #{channel.name}, ignoré.")

    await ctx.send(f"🎉 Scan terminé. {total_archived} messages archivés au total.")

# ============================
# LANCEMENT DU BOT
# ============================

bot.run("MTQyMzIyMTU2MjQ2MjQzNzM5Ng.GPVwdn.71dlmYUjDRnLkrWzRYWVIQ8w_E11VlZlUjNJQQ")
