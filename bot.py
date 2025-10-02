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

    # Table principale pour stocker les messages archivés
    cursor.execute('''CREATE TABLE IF NOT EXISTS archived_messages (
                        id INTEGER PRIMARY KEY,
                        message_id INTEGER UNIQUE,
                        content TEXT,
                        reactions INTEGER,
                        channel_id INTEGER,
                        server_id INTEGER,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    # Table secondaire pour suivre l'avancement du scan par salon
    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_progress (
                        channel_id INTEGER PRIMARY KEY,
                        last_message_id INTEGER
                    )''')

    conn.commit()
    conn.close()

# Archive un message dans la base
def archive_message(message_id, content, reactions, channel_id, server_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO archived_messages 
                      (message_id, content, reactions, channel_id, server_id)
                      VALUES (?, ?, ?, ?, ?)''',
                   (message_id, content, reactions, channel_id, server_id))
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
                message.guild.id
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
async def archive(ctx, message_id: int):
    """Archive manuellement un message avec son ID."""
    try:
        message = await ctx.channel.fetch_message(message_id)

        if message.author.bot:
            await ctx.send("⚠️ Ce message a été posté par un bot, il ne peut pas être archivé.")
            return

        if not is_message_archived(message.id):
            max_reactions = max([r.count for r in message.reactions], default=0)
            archive_message(message.id, message.content, max_reactions, message.channel.id, message.guild.id)
            await ctx.send(f"💾 Message archivé manuellement : {message.content[:50]}...")
        else:
            await ctx.send("⚠️ Ce message est déjà archivé.")
    except discord.NotFound:
        await ctx.send("⚠️ Message introuvable.")

# Vue avec boutons pour voter sur l'identité de l'auteur (optionnel)
class VoteView(View):
    def __init__(self, message_id, choices):
        super().__init__()
        self.message_id = message_id
        for name in choices:
            self.add_item(Button(label=name, style=discord.ButtonStyle.primary))

@bot.command()
async def show_message(ctx, message_id: int):
    """Affiche anonymement un message archivé (par son ID)."""
    content = get_archived_message(message_id)
    if content:
        content_anonymized = content[:200]
        users = ["User1", "User2", "User3"]  # À personnaliser
        view = VoteView(message_id, users)
        await ctx.send(f"📄 **Message anonymisé :**\n{content_anonymized}", view=view)
    else:
        await ctx.send("⚠️ Message non trouvé dans la base.")

@bot.command()
async def random_message(ctx):
    """Affiche un message archivé aléatoire de façon anonymisée."""
    result = get_random_archived_message()
    if result:
        message_id, content = result
        content_anonymized = content[:200]
        users = ["User1", "User2", "User3"]
        view = VoteView(message_id, users)
        await ctx.send(f"🎲 **Message aléatoire :**\n{content_anonymized}", view=view)
    else:
        await ctx.send("⚠️ Aucun message archivé pour le moment.")

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
                            channel.id,
                            ctx.guild.id
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
