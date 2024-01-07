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
