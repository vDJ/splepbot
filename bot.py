import discord
from discord.ext import commands
from discord.ui import Button, View
import sqlite3
import asyncio
import random
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ============================
# CONFIGURATION DU BOT
# ============================

# Initialisation des intents (tous activés pour permettre la lecture des messages, des réactions, etc.)
intents = discord.Intents.all()

# Création de l'instance du bot avec le préfixe '!'
bot = commands.Bot(command_prefix='!', intents=intents)

# Seuil par défaut de réactions pour l'archivage automatique
reaction_threshold = 4

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
                        image_url TEXT, 
                        reaction_emoji TEXT,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_progress (
                        channel_id INTEGER PRIMARY KEY,
                        last_message_id INTEGER
                    )''')

    conn.commit()
    conn.close()

# Archive un message dans la base, avec adresse de l'image si disponible
def archive_message(message_id, content, reactions, channel_id, server_id, author_name, message_url, image_url=None, reaction_emoji=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO archived_messages 
                      (message_id, content, reactions, channel_id, server_id, author_name, message_url, image_url, reaction_emoji)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (message_id, content, reactions, channel_id, server_id, author_name, message_url, image_url, reaction_emoji))
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
    
    if not message.content or message.content.strip() == "":
        return  # Ignore messages sans texte


    # Si le message atteint le seuil de réactions
    if reaction.count >= reaction_threshold:
        if not is_message_archived(message.id):
            # À placer juste avant l'appel à archive_message
            image_url = None
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith("image/"):
                        image_url = attachment.url
                        break

            archive_message(
                message.id,
                message.content,
                reaction.count,
                message.channel.id,
                message.guild.id,
                message.author.name,
                f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}", 
                image_url,
                str(reaction.emoji)
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
    
    if not target_message.content or target_message.content.strip() == "":
        await ctx.send("⚠️ Ce message ne contient pas de texte, il ne sera pas archivé.")
        return

    # À placer juste avant l'appel à archive_message
    image_url = None
    if target_message.attachments:
        for attachment in target_message.attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                image_url = attachment.url
                break


    max_reactions = max([r.count for r in target_message.reactions], default=0)
    url = f"https://discord.com/channels/{target_message.guild.id}/{target_message.channel.id}/{target_message.id}"
    archive_message(
        target_message.id,
        target_message.content,
        target_message.reactions,
        target_message.channel.id,
        target_message.guild.id,
        target_message.author.name,
        url,
        image_url,
        str(target_message.reaction.emoji)
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
    cursor.execute('SELECT message_id, content, message_url, image_url, reaction_emoji FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    result = cursor.fetchone()
    conn.close()

    if result:
        message_id, content, url, image_url, reaction_emoji = result
        content_anonymized = content[:200]
        
        embed = discord.Embed(
            title="🎲 Message aléatoire",
            description=content_anonymized,
            color=discord.Color.blurple()
        )
        if reaction_emoji:
            embed.add_field(name="Réaction", value=reaction_emoji, inline=True)
        
        embed.add_field(name="Lien", value=f"[Voir sur Discord]({url})", inline=False)

        if image_url:
            embed.set_image(url=image_url)

        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Aucun message archivé pour le moment.")


# Création d'une View custom pour gérer le vote
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



@bot.command()
async def random_message_poll(ctx):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT message_id, content, author_name, message_url, image_url, reaction_emoji FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    row = cursor.fetchone()
    if not row:
        await ctx.send("⚠️ Aucun message archivé pour le moment.")
        conn.close()
        return
    message_id, content, true_author, message_url, image_url, reaction_emoji = row

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
    message = await ctx.send(embed=embed, view=voting_view)
    voting_view.message = message


@bot.command() #scan un canal (1000 derniers messages ou 14 derniers jours, pas sûr)
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

        if not message.content or message.content.strip() == "":
            continue  # Ignore messages sans texte

        for reaction in message.reactions:
            if reaction.count >= reaction_threshold:
                # À placer juste avant l'appel à archive_message
                image_url = None
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith("image/"):
                            image_url = attachment.url
                            break

                archive_message(
                    message.id,
                    message.content,
                    reaction.count,
                    channel.id,
                    ctx.guild.id,
                    message.author.name,
                    f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message.id}",
                    image_url,
                    str(reaction.emoji)
                )
                total_archived += 1
                break

        update_last_scanned_id(channel.id, message.id)

        counter += 1
        if counter % 500 == 0:
            await asyncio.sleep(2)  # Pause anti rate-limit

    await ctx.send(f"✅ Scan terminé sur {channel.mention}, {total_archived} messages archivés.")


@bot.command() #scan tous les canaux (1000 derniers messages ou 14 derniers jours, pas sûr)
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

                if not message.content or message.content.strip() == "":
                    continue  # Ignore messages sans texte

                for reaction in message.reactions:
                    if reaction.count >= reaction_threshold:
                        # À placer juste avant l'appel à archive_message
                        image_url = None
                        if message.attachments:
                            for attachment in message.attachments:
                                if attachment.content_type and attachment.content_type.startswith("image/"):
                                    image_url = attachment.url
                                    break
                        archive_message(
                            message.id,
                            message.content,
                            reaction.count,
                            message.channel.id,
                            message.guild.id,
                            message.author.name,
                            f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}",
                            image_url,
                            str(reaction.emoji)
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

@bot.command() #scan TOUS les messages d'un canal (peut être long)
@commands.has_permissions(administrator=True)
async def scan_full(ctx, channel: discord.TextChannel):

    await ctx.send(f"📜 Début du scan complet du canal {channel.mention}...")

    total_archived = 0
    scanned = 0
    last_message = None

    try:
        while True:
            # On récupère 100 messages à partir du plus récent ou du message précédent
            messages = [m async for m in channel.history(limit=100, before=last_message)]
            if not messages:
                break  # plus de messages à traiter

            for message in messages:
                scanned += 1

                if message.author.bot:
                    continue

                if is_message_archived(message.id):
                    continue

                if not message.content or message.content.strip() == "":
                    continue

                for reaction in message.reactions:
                    if reaction.count >= reaction_threshold:
                        # À placer juste avant l'appel à archive_message
                        image_url = None
                        if message.attachments:
                            for attachment in message.attachments:
                                if attachment.content_type and attachment.content_type.startswith("image/"):
                                    image_url = attachment.url
                                    break

                        message_url = f"https://discord.com/channels/{ctx.guild.id}/{channel.id}/{message.id}"
                        archive_message(
                            message.id,
                            message.content,
                            reaction.count,
                            channel.id,
                            ctx.guild.id,
                            message.author.name,
                            message_url,
                            image_url,
                            str(reaction.emoji)
                        )
                        total_archived += 1
                        break

                # Pour permettre la pagination "before="
                last_message = message

            # Pause tous les 1000 messages
            if scanned % 1000 == 0:
                await ctx.send(f"⏳ {scanned} messages scannés dans {channel.mention}, {total_archived} archivés...")
                await asyncio.sleep(3)

        await ctx.send(f"✅ Scan terminé dans {channel.mention} : {scanned} messages scannés, {total_archived} archivés.")

    except discord.Forbidden:
        await ctx.send("❌ Je n'ai pas accès à ce canal.")
    except Exception as e:
        await ctx.send(f"⚠️ Erreur pendant le scan : {e}")



# ============================
# LANCEMENT DU BOT
# ============================

bot.run(TOKEN)
