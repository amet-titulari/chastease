# Roadmap Completed – Chastease

Archiv der bereits erledigten Roadmap-Punkte. Die offene Planung liegt in [ROADMAP.md](ROADMAP.md).

## Umgesetzter Stand (v0.5.0+, März 2026)

- FastAPI-Backend mit 18 Routern, 36 Services und 25 Model-Dateien
- Alembic-Stand konsolidiert: Baseline `0031`, danach `0032` (`phase_state_json`) und `0033` (Phasen-Targets-Backfill)
- Session-Lifecycle: Erstellen, Vertrag, Timer, Events, Export (PDF/JSON)
- KI-Provider: xAI/Grok, OpenRouter, Ollama, Stub – inkl. Action-Normalisierung
- Modularer System-Prompt (Persona, Wearer, Safety, Session, Style, Scenario) mit externen Prompt-Dateien und Versions-Logging
- Expliziter Action-Contract im Prompting für strukturierte Task-Auslösung
- Kontextfenster-Management mit Trunkierung und Zusammenfassung
- Aufgabensystem: CRUD, Konsequenzen, Psychogramm-Multiplikatoren, Overdue-Sweep
- Task-Actions: `create_task`, `update_task`, `fail_task` inkl. Audit-/System-Events und Pydantic-Validierung am KI-Rand
- Deadline-Robustheit: explizites `deadline_minutes` (`int/null`), Zeitkontext (UTC + lokal + TZ) im KI-Kontext
- Spiele-Erweiterung gestartet: API-Basis für Posture Training (Programm-Katalog + Session-Start erzeugt Aufgaben)
- Bildverifikation: heuristische + Vision-API-basierte Plomben-Analyse
- Hygiene-Öffnungen: Kontingente, Countdown, Overrun-Strafen
- Sicherheitssystem: Ampel (G/Y/R), Safeword, Emergency Release, Safety-Override im Prompt
- WebSocket: Chat-Stream, proaktive Reminder, Timer-Ticks
- Voice: OpenAI-Realtime-Audio + TTS
- Web-UI: Landing, Setup-Wizard, Experience-Onboarding, Play-Modus, Profil, History, Contracts, Personas, Scenarios, Inventory
- Play-Modus: inline Action Cards (mit Task-Nr., Deadline, kontextabhängige Buttons), Tasks-Dropdown mit interaktiven Cards, Persona-Avatar im Chat
- UI-Refresh: konsolidierte Design-Tokens, modernisierte Navigation und vereinheitlichte Hauptoberflächen
- Persona-/Scenario-Verwaltung: CRUD, Presets, SillyTavern-Import/Export
- Inventar: Items, Scenario-Links, Session-Items
- Persistenter Roleplay-State pro Session: Relationship, Protocol und Scene inkl. Prompt-Integration
- Persistenter Phasen-State pro Session: eigene Phasenpunkte und Zielwerte getrennt von der Gesamtbeurteilung
- Director-Schicht im Prompting ergänzt, getrennt von Persona-/Session-Kontext
- Session-Status im Play-UI als diskretes Popup statt als großer Chat-Block
- HTMX-Partials für Profil-Sessionübersicht sowie Listen in Personas, Scenarios und Inventory
- Scenario-Editor mit editierbaren Phasen-Zielwerten, Gewichtung und Mindestdauer
- Media: Avatar-Upload, Content-Serving
- Browser Push Notifications (Web Push + VAPID)
- Auth: Register/Login, moderne Passwort-Hashes via `pwdlib`/Argon2, httpOnly-Cookie, Multi-Device-Support
- Audit-Logger (opt-in, JSON-Lines)
- Testdaten-Hygiene: automatische DB-Bereinigung nach Testlauf (session-scope cleanup)
- Frische virtuelle Umgebung aus `requirements.txt` validiert und als Projekt-`.venv` neu aufgebaut
- Docker-Deployment (Dockerfile + docker-compose)
- Teststatus: 31+ Testmodule (lokale automatisierte Tests, inkl. Prompt-/Action-Metadaten)

### v0.4 – Device Foundation

- [x] Lovense-Basisintegration fuer Web/Dashboard
- [x] Wearer-Profil um Device-/Tool-Auswahl und bevorzugte Toy-Konfiguration erweitern
- [x] Eigene Toy-Presets speichern und verwalten
- [x] Toy-Presets pro Keyholder-Profil hinterlegen
- [x] Toy-Status im Play-Modus sichtbar machen
- [x] Toy-Kommandos als Session-Actions/Audit-Events persistieren
- [x] Toy-Simulator fuer lokale Entwicklung
- [x] Safety-Limits und Freigaberegeln fuer Toy-Steuerung
- [x] Admin-Programm-/Pattern-Editor fuer Lovense anbieten, wenn im Wearer-Profil Lovense/Toys aktiviert sind
- [x] KI darf in der Session freigegebene Toy-Presets ausloesen

---

## Phase 0: Fundament

- [x] Python-Projekt aufsetzen (FastAPI, SQLAlchemy, Alembic)
- [x] SQLite-Datenbank & erstes Schema (Session, Persona, Message, PlayerProfile, Contract)
- [x] Alembic Migrationen einrichten
- [x] Basis-Jinja2-Template mit einfacher CSS-Testoberflaeche
- [x] `.env`-Konfiguration & Pydantic Settings
- [x] `data/`-Verzeichnis in `.gitignore`
- [x] Client-Privacy-Baseline: kein LocalStorage, kein IndexedDB, kein Service-Worker-Cache
- [x] Upload-Pfad für Verifikationsbilder so definieren, dass keine bewusste Galerie-Speicherung durch die App erfolgt
- [x] HTMX/Server-Partials dort ausgerollt, wo der Pflegegewinn klar ist (Profil-Sessionübersicht, Personas, Scenarios, Inventory)
- [x] Alpine.js fuer kleine lokale UI-Zustaende evaluiert und bewusst nicht eingefuehrt; Vanilla JS + punktuelles HTMX bleiben ausreichend

Deliverable erreicht: `python -m uvicorn app.main:app` startet ohne Fehler.

---

## Phase 1: KI-Integration & Chat

- [x] `AIGateway`-Abstraktion implementieren
- [x] OpenAI-kompatibler Provider (xAI/Grok, OpenRouter) implementiert
- [x] Persona-Builder: System-Prompt aus Konfiguration generieren
- [x] Spieler-Psychogramm modellieren und Onboarding-Fragebogen definieren
- [x] Player-Profile in den Prompt-Kontext integrieren
- [x] Chat-Router & WebSocket-Verbindung
- [x] Chat-Interface (Jinja2 + JS-Testkonsole inkl. WebSocket-Live-Feed)
- [x] Persona-Konfigurationsseite
- [x] Spielerprofil-Konfigurationsseite
- [x] KI-Konfigurationsseite (API-Key, Modell)

Deliverable erreicht: Gespräch mit konfigurierter Keyholderin möglich.

---

## Phase 2: Session-Mechanik & Timer

- [x] Session-Start mit Konfiguration (Min/Max-Dauer, zufällige Bestimmung)
- [x] Vertragsgenerator als letzter Setup-Schritt vor Sessionstart (aktuell AI-Stub)
- [x] Digitale Unterzeichnung und Start-Gating: Session beginnt erst nach Signatur
- [x] Vertrags-Snapshot und Unveränderlichkeit nach Signatur
- [x] Vertrags-Addenda für KI-initiierte Änderungen mit explizitem Consent
- [x] Timer-Service: läuft im Background via APScheduler
- [x] Timer-Operationen: add/remove/freeze/unfreeze
- [x] Timer-Anzeige im Dashboard (WebSocket-Updates)
- [x] Session-Status-Maschine (active / paused / emergency/safeword/pause)
- [x] Session-Verlauf / Event-Log
- [x] Session regulär beenden (automatisch bei Timer-Ablauf)

Deliverable erreicht: Vollständiger Session-Lifecycle funktioniert.

---

## Phase 3: Aufgaben & Belohnungssystem

- [x] Task-Datenmodell & CRUD
- [x] KI kann Tasks via Structured Output vergeben
- [x] KI kann bestehende Tasks via `update_task` aktualisieren (Titel/Beschreibung/Deadline)
- [x] Task-Anzeige im UI (Aufgabenliste)
- [x] Task als erledigt markieren
- [x] Automatische Konsequenzen bei Failure / Overdue (Lock-Verlaengerung)
- [x] Psychogramm-gesteuerte Aufgaben- und Straflogik anwenden
- [x] Belohnungs/Bestrafungs-Events im Verlauf dokumentieren
- [x] KI-Antworten inkl. Actions-Schema stabil

Deliverable erreicht: Vollständiges Task-&-Consequence-System.

---

## Phase 4: Sicherheitssystem

- [x] Ampelsystem (Gelb/Rot API implementiert; UI-Testkonsole vorhanden)
- [x] Gelb: KI-Prompt-Override für Fürsorge-Modus
- [x] Rot: Session pausieren (API)
- [x] Safeword: sofortiger Session-Stop (API)
- [x] Emergency Release: Pflichtbegründung (API)
- [x] Safety-Log: alle Ereignisse werden gespeichert
- [x] Safety-Override im System-Prompt verankert

Deliverable erreicht: Alle Safety-Features vollständig und geprüft.

---

## Phase 5: Bildverifikation & Benachrichtigungen

- [x] Bild-Upload-Endpoint (lokal, UUID-Dateiname)
- [x] KI-Bildanalyse-Integration (Verifikation, heuristische Logik + optionaler Ollama-Provider mit Fallback)
- [x] Optionale Seal-Nummer in Verifikationsanfrage
- [x] Verifikations-UI (Testkonsole)
- [x] Hygiene-Öffnungen: Kontingente pro Tag/Woche/Monat implementieren
- [x] Hygiene-Öffnungen: Countdown, Wiederverschluss-Bestätigung und automatische Bestrafung bei Überziehung
- [x] Plomben-Historie: Zerstörung alter Plombe und Pflicht-Eintrag neuer Plombe nach Öffnung
- [x] APScheduler-Basis: periodischer Task-Overdue-Sweep für aktive Sessions
- [x] APScheduler: proaktive Keyholderin-Nachrichten
- [x] Browser Push Notifications (Web Push API)
- [x] Konfigurierbare Benachrichtigungs-Haeufigkeit (Intervall/Cooldown per `.env`)

Deliverable erreicht: Keyholderin agiert proaktiv, Verifikation funktioniert.

---

## Phase 6: Polish & Testing

- [x] Responsive Design (Mobile-Optimierung)
- [x] Error Handling & User Feedback
- [x] Session-History-Seite
- [x] Vertragsansicht inkl. Addenda und Export
- [x] Persona-Bibliothek (mehrere gespeicherte Personas)
- [x] Ollama-Provider implementieren
- [x] Unit/Integration Tests kritischer Services und Flows (Timer, Safety, Contract, Hygiene, Verification)
- [x] Dokumentation finalisieren

Deliverable erreicht: MVP – vollständig funktionsfähig.

---

## Backlog (bereits umgesetzt)

### v0.1 – Qualität
- [x] Kontext-Window-Management (Session-Zusammenfassungen)
- [x] Aufgaben-Bibliothek (vordefinierte Tasks pro Persona, API + Chat-Inspirationskontext)

### v0.2 – UX
- [x] Session-Export (als Text/PDF)
- [x] Persona-Verwaltung (CRUD, Import/Export)
- [x] Inventar-Verwaltung (Items, Scenario-Links, Session-Items)
- [x] Aufgaben-System (CRUD, Aktionskarten, Deadline-Handling)

### v0.3 Erweiterungen – Spiele
- [x] Trainingsidee 1: Posture Training - API-Basis (Programm-Katalog + Run-Start)
- [x] Geführtes und überwachtes Training (Game-Screen mit Gesamt-Timer, aktueller Posture, Auto-Capture)
- [x] Variable Retry-Zeit je Schwierigkeitsgrad (easy/medium/hard)
- [x] Max-Misses-Regel mit Session-Penalty und Abschlussbericht

### v0.3.1 API Anpassungen
- [x] Namensgebung bei Kontroll- und Spielverifikationsbildern auf SessionID-GameID-RunNumber-yyyymmdd-hhmm
- [x] Hygiene-Öffnung anzeigen, wann nächste Öffnung erlaubt ist, wenn aktuelles Kontingent Tag/Woche/Monat ausgeschöpft ist
- [x] Eigenes Modul für Postures im Inventar (z. B. `/api/inventory/postures`)
- [x] Posture-Matrix in Inventar-Modul Posture verschieben
- [x] API-Key-Verschlüsselung (Fernet)
- [x] API `/api/sessions/blueprints` nur für eigenen User ermöglichen
- [x] API `/api/sessions/{session_id}` nur für eigene Sessions des Users
- [x] API-Absicherung für Admin-/Pflege-Endpunkte via Login und Rollenprüfung
- [x] Postures Import/Export als ZIP-Workflow inkl. Referenzdaten und Medien
- [x] Spiel-UI auf `available`-Posture-Endpoints im Inventar-Modul umgestellt
- [x] Verbliebene Legacy-Posture-Routen unter `/api/games/...` explizit als deprecated markiert und auf das Inventar-Modul verwiesen

### v0.3.2 – AI & Modularität
- [x] Prompt-Dateien nach `app/prompts/` ausgelagert (Base, Persona, Safety, Session, Style, Scenario)
- [x] Prompt-Version und verwendete Templates beim Rendern loggen
- [x] KI-Task-Actions als Pydantic-Modelle mit zentraler Normalisierung/Validierung
- [x] LiteLLM als gemeinsamer LLM-Client eingeführt und Provider-Code darauf konsolidiert
- [x] Prompt-Metadaten persistent pro Message speichern und per Chat-API ausliefern
- [x] Chat-Metadaten im UI reduziert und auf sprechende Namen umgestellt
- [x] Action-Contract im Prompting ergänzt, damit Aufgaben im Live-Chat zuverlässiger als strukturierte Actions ausgelöst werden
- [x] Task-Template-Pool für reproduzierbare Schwierigkeit und Persona-spezifische Vorschläge aufgebaut
- [x] Persistenter Roleplay-State für Relationship / Protocol / Scene eingeführt
- [x] `update_roleplay_state`-Action für KI-seitige Session-State-Updates ergänzt
- [x] Director-Guidance im Prompting ergänzt
- [x] Roleplay-State wird jetzt auch ereignisgetrieben aus Task-Completion, Task-Fail/Overdue, Verifikationen und Spielberichten fortgeschrieben
- [x] `Orders` im UI/Prompting in `Offene Anweisungen` umbenannt und klarer von formalen Tasks getrennt
- [x] Scene-/Protocol-State im Dashboard und in der Play-Ansicht verdichtet und direkt sichtbar gemacht
- [x] Sessionuebergreifende Beziehungsdynamik als `relationship_memory` fuer Prompting, API und UI ergaenzt

### v0.3.3 – HTMX & Backoffice-UX
- [x] HTMX für Profil-Sessionübersicht eingeführt
- [x] HTMX-Partials für Persona-Liste eingeführt
- [x] HTMX-Partials für Scenario-Liste eingeführt
- [x] HTMX-Partials für Inventory-Liste eingeführt
- [x] Frische `.venv` aus `requirements.txt` aufgebaut und validiert
