# C4 - Component View (Backend)

Dieses Diagramm zeigt die internen Komponenten der Python-API.
Die KI-Komponente steht im Zentrum der Entscheidungs- und Narrationslogik.

## Rollenmodell

- `Wearer`: menschliche Spielerrolle, steuert einen Charakter.
- `Keyholder`: wird durch die KI uebernommen und steuert Gegenpart, Dynamik und Reaktionen.
- Jeder `Wearer` ist genau einer aktiven `Session` zugeordnet.

```mermaid
flowchart LR
    Wearer["Wearer (User)"] --> Api["API Layer\n/api/v1"]

    subgraph Backend["Chastease Backend (Python API)"]
      Api --> Sessions["domains/sessions\nSession Orchestrator"]
      Api --> Characters["domains/characters"]
      Api --> Quests["domains/quests"]
      Api --> Setup["domains/sessions\nSetup Agent"]

      Setup --> Policy["services/ai\nPolicy Builder"]
      Setup --> IntegrationSetup["services/integrations\nProvisioning Service"]
      Sessions --> Policy["services/ai\nPolicy Engine"]
      Sessions --> AI["services/ai\nKeyholder Engine (central)"]
      Characters --> AI
      Quests --> AI

      AI --> Actions["services/ai\nAction Gateway"]
      Actions --> TTLock["integrations/ttlock\nAdapter"]
      Actions --> Chaster["integrations/chaster\nAdapter (optional)"]
      Actions --> Emlalock["integrations/emlalock\nAdapter (optional)"]
      IntegrationSetup --> Chaster
      IntegrationSetup --> Emlalock
      AI --> Vision["services/ai\nImage Review Service"]

      Sessions --> Repos["repositories"]
      Characters --> Repos
      Quests --> Repos
      Policy --> Repos
      Actions --> Repos
      Vision --> Repos

      AI --> Shared["shared\nschemas, events, guards"]
      Policy --> Shared
      Actions --> Shared
      Sessions --> Shared
      Characters --> Shared
      Quests --> Shared

      Sessions --> Audit["shared/audit\nAction & Decision Log"]
      AI --> Memory["shared/memory\nAI Memory Protocol"]
    end

    AI --> LLM["OpenAI API"]
    Vision --> LLM
    Repos --> DB[(PostgreSQL)]
    TTLock --> TTApi["TTLock API"]
    Chaster --> ChApi["Chaster API"]
    Emlalock --> EmApi["Emlalock API"]

    AI -. "uebernimmt Rolle:\nKeyholder" .-> Keyholder["Keyholder (AI Role)"]
    Wearer -. "genau 1 aktive Session" .-> Sessions
    Wearer -. "Hard-Stop optional\n(Setup-Policy)" .-> Policy
```

## Verantwortlichkeiten pro Komponente

- `api/`:
  - HTTP-Eintrittspunkt, Auth, Validierung, Response-Mapping
- `domains/sessions/`:
  - Session-Lifecycle, Setup-Flow, Turn-Orchestrierung, Wearer-Session-Bindung
- `domains/characters/`:
  - Charakterwerte, Progression, regelrelevante Attribute
- `domains/quests/`:
  - Questzustand, Trigger, Fortschritt
- `services/ai/`:
  - Keyholder-Logik, Policy-Entscheidung, Prompting, Guardrails, Antwortnormalisierung
- `services/ai Action Gateway`:
  - policy-gepruefte Aktionsausfuehrung (`execute`/`suggest`)
- `services/ai Image Review`:
  - automatisierte Beurteilung von Kontrollbildern
- `integrations/*`:
  - externe API-Adapter, Integrationen benutzerwaehlbar und parallel nutzbar
- `services/integrations Provisioning`:
  - automatische Session-Anlage bei Chaster/Emlalock waehrend Setup (soweit API-seitig moeglich)
- `repositories/`:
  - persistenter Zugriff auf Sessions, Turns, Policy, Charakter- und Questzustand
- `shared/`:
  - moduluebergreifende DTOs, Events, Fehlercodes, Audit und Memory-Protokoll

## Wichtige Architekturregeln

- KI-Interaktion laeuft ausschliesslich ueber `services/ai/`.
- Domain-Module sprechen nicht direkt mit externen APIs.
- Persistenzzugriffe laufen ausschliesslich ueber `repositories/`.
- TTLock-Aktionen fuer Oeffnen/Schliessen erfordern 2-Phasenfreigabe.
- Hard-Stop (falls aktiviert) setzt externe Integrationen in sicheren Zustand.
