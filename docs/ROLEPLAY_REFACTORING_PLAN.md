# Roleplay Refactoring Plan

## Ziel

Chastease soll von einem KI-gestuetzten Session-Chat mit Domänenlogik zu einer klar strukturierten Roleplay-Anwendung weiterentwickelt werden.
Der Kern bleibt sicherheits-, policy- und audit-orientiert, bekommt aber einen expliziten Roleplay-Layer fuer Charaktere, Szenarien, Memory und dramaturgische Steuerung.

Diese Datei dient als Vorbereitung fuer ein groesseres Refactoring. Sie beschreibt das Zielbild, die Modulgrenzen und eine empfohlene Migrationsreihenfolge.

## Warum das Refactoring sinnvoll ist

Der aktuelle Stand hat bereits starke RP-Bausteine:

- persistente Sessions
- Turn-Historie
- Psychogramm und Policy-Snapshots
- zustandsabhaengige Aktionen
- LLM-Profil je User

Was noch fehlt, ist eine klare fachliche Trennung zwischen:

- Sicherheits- und Vertragslogik
- Session-State und Runtime-Aktionen
- eigentlicher Roleplay-Inszenierung
- Charakter-/Szenario-Autorensystem
- Langzeit-Memory und Kontextaufbereitung fuer LLMs

Ohne diese Trennung drohen drei Probleme:

- Prompts werden immer groesser und schwerer wartbar
- RP-Verhalten bleibt implizit in verstreuter Logik verborgen
- neue Features wie Character Cards, Lorebooks oder Multi-Charakter-Szenarien lassen sich nur schwer sauber integrieren

## Zielbild

Die Anwendung soll aus fuenf fachlichen Ebenen bestehen:

1. Consent and Safety Layer
- Consent, Grenzen, Trigger, Verbote, Hard-Stop, Audit
- bleibt autoritativ und serverseitig erzwungen

2. Session and Runtime Layer
- aktive Session, Turn-Historie, Timer, Seal, Hygiene, Integrationen, Pending Actions
- ist die alleinige Wahrheit fuer den aktuellen Zustand

3. Roleplay Engine Layer
- Character Persona
- Scenario Template
- Scene State
- Narrative Mode
- Prompt Assembly
- Summary and Memory

4. Model Gateway Layer
- OpenAI-kompatible Provider
- OpenRouter
- lokale Modelle via Ollama oder spaeter weitere Adapter

5. Experience Layer
- Chat-UI
- Character-/Scenario-Auswahl
- RP-spezifische Session-Ansichten
- Admin- und Debug-Ansichten fuer Prompt, Memory und Aktionen

## Was aus SillyTavern-artigen Systemen uebernommen werden sollte

Es geht nicht darum, SillyTavern als Hauptsystem einzubauen. Uebernommen werden sollten nur bewaehrte Konzepte:

- Character Cards als Autorenformat
- Persona-Layer getrennt vom technischen Psychogramm
- Lorebook oder World Info fuer regel- und szenarioabhaengige Kontextmodule
- Session Summary und Long-Term Memory
- Prompt-Presets fuer verschiedene RP-Modi
- optionale Slash-Commands oder Makros als UI-Hilfe

Nicht uebernommen werden sollte:

- eine zweite freie Wahrheitsquelle neben der Session-Engine
- clientseitige Aktionslogik ohne serverseitige Validierung
- eine enge Kopplung an eine externe RP-UI

## Zielmodule

Empfohlene Zielstruktur innerhalb von `src/chastease/`:

- `api/`
- `domains/consent/`
- `domains/sessions/`
- `domains/runtime_actions/`
- `domains/roleplay/`
- `domains/characters/`
- `domains/scenarios/`
- `services/ai/`
- `connectors/`
- `repositories/`
- `web/`
- `shared/`

### Neue Fachmodule im Detail

#### `domains/roleplay/`

Verantwortlich fuer:

- Prompt-Assembly fuer RP-Turns
- Narrative Modifiers
- Szenenwechsel
- dramaturgische Zustandsfuehrung
- Summary-Erzeugung
- Context-Budgeting fuer LLM-Aufrufe

Beispielobjekte:

- `RoleplayContext`
- `SceneState`
- `NarrativeDirective`
- `MemorySnapshot`
- `PromptPackage`

#### `domains/characters/`

Verantwortlich fuer:

- Character Cards
- Persona-Profile
- Stil, Tonalitaet, Dominanzstil, ritualisierte Sprache
- Einleitungstexte und Greeting-Templates

Beispielobjekte:

- `CharacterCard`
- `PersonaProfile`
- `SpeechStyle`

#### `domains/scenarios/`

Verantwortlich fuer:

- Szenario-Definitionen
- World Info
- Phasen eines RP-Szenarios
- Trigger fuer Kontextbausteine

Beispielobjekte:

- `ScenarioDefinition`
- `LoreEntry`
- `ScenarioPhase`

## Neue Datenkonzepte

Folgende Konzepte sollten zunaechst als Datenmodell oder Snapshot eingefuehrt werden:

- `character_profile`
- `scenario_profile`
- `scene_state`
- `session_summary`
- `memory_entries`
- `prompt_profile`

Diese Konzepte muessen nicht sofort voll relational modelliert werden. Fuer die erste Refactoring-Stufe reichen saubere DTOs und JSON-Snapshots, solange Besitzverhaeltnisse und Verantwortungen klar sind.

## Empfohlene technische Leitlinien

- Psychogramm bleibt maschinenlesbar und regelorientiert.
- Persona bleibt erzählerisch und austauschbar.
- Session-State bleibt die kanonische Wahrheit.
- Prompt-Zusammenbau wird zentralisiert und versioniert.
- Jeder LLM-Turn bekommt nachvollziehbare Input-Bloecke mit klarer Herkunft.
- Safety- und Runtime-Regeln duerfen nie im Frontend oder allein im Prompt erzwungen werden.

## Refactoring-Stufen

### Stufe R2: Begriffe und Schnitte schaerfen

Ziel:

- bestehende Narration-Logik aus dem allgemeinen Service-Layer fachlich auftrennen
- RP-Begriffe im Code sichtbar machen

Arbeiten:

- `services/narration.py` in kleinere fachliche Bausteine zerlegen
- `StoryTurnContext` in Richtung `RoleplayContext` weiterentwickeln
- Prompt-Bausteine fuer Policy, Psychogramm, Live-Snapshot und History separat modellieren

### Stufe R3: Character and Scenario Layer einfuehren

Ziel:

- Character Cards und Szenario-Definitionen als eigene Konzepte verankern

Arbeiten:

- Character-Card-Datenmodell definieren
- Persona-Felder von Psychogramm-Feldern trennen
- Szenario-Bibliothek und Lorebook-Struktur einführen

### Stufe R4: Memory and Summary Layer einfuehren

Ziel:

- laengere RP-Sessions token-effizient und konsistent halten

Arbeiten:

- Session-Zusammenfassungen pro Abschnitt speichern
- Memory-Typen definieren: facts, vows, rituals, unresolved threads
- Memory-Auswahl vor LLM-Call zentralisieren

### Stufe R5: UI und Authoring modernisieren

Ziel:

- RP-Autorenwerkzeuge und immersive UI sauber auf die Backend-Faehigkeiten abbilden

Arbeiten:

- Character-/Scenario-Auswahl im Frontend
- RP-Modi und Prompt-Presets editierbar machen
- Prompt-Debug-Ansicht fuer Entwicklung und Tuning

## Konkrete erste Refactoring-Kandidaten im aktuellen Code

- `src/chastease/services/narration.py`
  - aktuell ueberladen mit Prompting, Kontextaufbereitung, Vertragslogik und Hilfsfunktionen
- `src/chastease/api/routers/chat.py`
  - enthaelt viel Aktions- und Parsinglogik, die schrittweise in Use-Cases oder Domain-Services wandern sollte
- `src/chastease/models.py`
  - noch ohne explizite RP-Modelle fuer Persona, Szenario und Summary
- `src/chastease/connectors/llm_connector.py`
  - sollte mittelfristig nur Gateway sein, nicht fachliche Kontextentscheidungen tragen

## Definition of Done fuer die Vorbereitungsphase

Die Vorbereitungsphase ist abgeschlossen, wenn:

- die RP-Zielarchitektur dokumentiert ist
- ein Refactoring-Backlog entlang fachlicher Schnitte existiert
- ein erster Zielbegriffssatz fuer Character, Scenario, Memory und Persona im Projekt verankert ist
- die naechste Implementierungsphase ohne Architektur-Grundsatzdiskussion gestartet werden kann

## Empfohlener Startpunkt

Als erster technischer Schritt sollte nicht sofort ein neues Frontend gebaut werden.
Der beste Startpunkt ist die Extraktion eines dedizierten Roleplay-Context-Builders aus der bestehenden Narration-Logik.

Danach folgen:

1. Character-Card-Schema
2. Scenario-/Lorebook-Schema
3. Session-Summary-Modell
4. Prompt-Assembler mit versionierten Bausteinen