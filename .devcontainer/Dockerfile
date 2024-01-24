# Verwenden Sie das offizielle Debian-Image als Basis
FROM debian:buster-slim

# Installieren Sie notwendige Pakete
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg2 \
    software-properties-common

# Fügen Sie das Docker-Repository hinzu und installieren Sie Docker
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - \
    && add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    && apt-get update \
    && apt-get install -y docker-ce docker-ce-cli containerd.io

# Starten Sie den Docker-Daemon
CMD ["dockerd"]
