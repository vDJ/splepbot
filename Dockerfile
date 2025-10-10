# Utilise une image Python officielle
FROM python:3.14-slim

# Crée un dossier de travail
WORKDIR /app

# Copie les fichiers
COPY . /app

# Installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Dossier pour la base de données (sera monté)
VOLUME /app/data

# Lance le bot
CMD ["python", "bot.py"]