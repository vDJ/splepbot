import sqlite3

DB_PATH = "data/messages.db"

# ============================
# INITIALISATION DE LA BASE
# ============================
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
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        times_polled INTERGER DEFAULT 0
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_progress (
                        channel_id INTEGER PRIMARY KEY,
                        last_message_id INTEGER
                    )''')

    conn.commit()
    conn.close()

# ============================
# FONCTIONS POUR L’ARCHIVAGE
# ============================

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

# Récupère le contenu d'un message archivé par son ID
def get_archived_message(message_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM archived_messages WHERE message_id = ?', (message_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Récupère un message aléatoire depuis la base
def get_random_archived_message():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT message_id, content FROM archived_messages ORDER BY RANDOM() LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return row if row else None

# ============================
# FONCTIONS POUR LE SCAN
# ============================

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
