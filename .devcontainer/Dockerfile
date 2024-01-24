# Verwenden Sie das offizielle Debian-Image als Basis
FROM debian:buster-slim

# Vermeiden Sie Warnungen durch fehlende lokale Einstellungen
ENV LANG C.UTF-8

# Installieren Sie notwendige Pakete
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg2 \
    software-properties-common \
    lsb-release

# Fügen Sie das Docker-Repository hinzu und installieren Sie Docker
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - \
    && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    && apt-get update \
    && apt-get install -y docker-ce docker-ce-cli containerd.io

# Installieren Sie Python 3 und Pip
RUN apt-get install -y python3 python3-pip \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && ln -s /usr/bin/pip3 /usr/bin/pip

# (Optional) Installieren Sie zusätzliche Python-Pakete
RUN pip install flask celery redis pipenv

# Setzen Sie das Arbeitsverzeichnis
WORKDIR /workspace

# Fügen Sie Ihr Anwendungsverzeichnis hinzu (optional, abhängig von Ihrer Anwendung)
COPY . /workspace

# Exponieren Sie notwendige Ports (abhängig von Ihrer Anwendung)
EXPOSE 5000

# Startbefehl (passen Sie dies an Ihre Anwendung an)
CMD ["python", "app.py"]
