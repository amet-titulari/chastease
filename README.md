# chastease

Chastease

## Docker

### Image Bulden

```Requirements im .venv erstellen
delete requirements.txt
pip freeze > requirements
```

```Docker
docker build -t eritque/chastease:latest .   
```

### Image hochladen

```Docker
docker login
docker push eritque/chastease:latest
```

## BABEL

### Initialisieren und Extrahieren der Sprachdatei

``` Text
# Extrahieren der Strings
pybabel extract -o messages.pot .

# Initialisieren der .po-Dateien für Deutsch
pybabel init -i messages.pot -d translations -l de_CH

# Initialisieren der .po-Dateien für English
pybabel init -i messages.pot -d translations -l en
```

### Aktualisieren und Extrahieren der Sprachdatei

``` Text
# Extrahieren der Strings
pybabel extract -o messages.pot .

# Aktualisieren der .po-Dateien für Deutsch
pybabel update -i messages.pot -d translations
```


### Kompilieren der Sprachdatei

``` Text
# Kompielieren der Sprachdatei
pybabel compile -d translations

```
