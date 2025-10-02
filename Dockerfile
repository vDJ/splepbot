# Utiliser l'image Python officielle
FROM python:3.9-slim

# Définir le répertoire de travail dans le container
WORKDIR /app

# Copier les fichiers du projet dans le container
COPY . /app

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Définir la commande par défaut pour exécuter le bot
CMD ["python", "bot.py"]