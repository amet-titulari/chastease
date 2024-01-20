# Basis-Image
FROM python:3.12.1-bullseye

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Kopieren Sie requirements.txt in das Arbeitsverzeichnis im Container
COPY requirements.txt .

# Installieren Sie die Abhängigkeiten
RUN pip install --no-cache-dir -r requirements.txt

# Kopieren Sie den restlichen Code in das Arbeitsverzeichnis im Container
COPY . .
COPY .env_prod .env

# Setzen Sie Umgebungsvariablen
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Port, auf dem der Container lauscht, freigeben
EXPOSE 5000

# Starten Sie die Anwendung mit Gunicorn
CMD flask db upgrade && gunicorn -w 4 -b 0.0.0.0:5000 app:app
