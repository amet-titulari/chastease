# UML - Domain Model (MVP)

Das Klassendiagramm beschreibt das fachliche Kernmodell fuer den MVP.

```mermaid
classDiagram
    class User {
      +UUID id
      +string email
      +datetime created_at
    }

    class Character {
      +UUID id
      +UUID user_id
      +string name
      +int strength
      +int intelligence
      +int charisma
      +int hp
    }

    class ChastitySession {
      +UUID id
      +UUID user_id
      +UUID character_id
      +string status
      +json session_state
      +datetime created_at
      +datetime updated_at
    }

    class Turn {
      +UUID id
      +UUID session_id
      +int turn_no
      +string player_action
      +string ai_narration
      +json rule_outcome
      +datetime created_at
    }

    User "1" --> "0..*" Character
    User "1" --> "0..*" ChastitySession
    Character "1" --> "0..*" ChastitySession
    ChastitySession "1" --> "0..*" Turn
```

## Modellregeln (MVP)

- Jede Session besitzt genau einen `session_state`-Container fuer persistente Laufzeitdaten.
- Turn-Nummern sind je Session eindeutig und aufsteigend.
- Eine Session ist einem Character zugeordnet und laeuft unter genau einem User.
