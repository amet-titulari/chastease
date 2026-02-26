````markdown
# UML - Sequence: DevOps Manual Image Build (GHCR)

Sequenz fuer den manuellen GitHub-Workflow zum Bauen und Veroeffentlichen des Docker-Images.

```mermaid
sequenceDiagram
    actor Maintainer
    participant GH as GitHub Actions
    participant Runner as Build Runner
    participant Docker as Buildx
    participant GHCR as GitHub Container Registry

    Maintainer->>GH: Workflow "Manual Docker Image Build" starten
    GH->>Runner: Job initialisieren (workflow_dispatch inputs)
    Runner->>Docker: Buildx Setup
    Runner->>GHCR: Login mit GITHUB_TOKEN (packages:write)
    Runner->>Docker: Image bauen (Dockerfile)
    Docker->>GHCR: Push ghcr.io/<owner>/<repo>:<tag>
    alt push_latest=true
        Docker->>GHCR: Push :latest
    end
    GH-->>Maintainer: Summary mit publiziertem Image-Tag
```

## Kernregeln

- Workflow ist manuell triggerbar (`workflow_dispatch`).
- Registry-Ziel ist GHCR im selben Repository-Namespace.
- Berechtigungen: `contents:read`, `packages:write`.

````
