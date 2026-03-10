# Roadmap – Chastease

## Entwicklungsphasen

## Stand (Alpha)

- Implementiert: FastAPI-Grundgeruest, SQLAlchemy-Modelle, Alembic-Migrationen `0001`-`0006`, Session/Contract/Hygiene/Safety/Verification/Chat/Tasks APIs
- Implementiert: APScheduler-Jobs fuer Task-Overdue-Sweep und proaktive Keyholderin-Reminder
- Implementiert: WebSocket-Live-Streaming fuer neue Assistant-Nachrichten inkl. proaktiver Reminder
- Implementiert: Interaktive Web Test Console im Dashboard fuer manuelle End-to-End-Tests
- Implementiert: Basis-Absicherung fuer Chat-WebSocket per persistentem Session-Token
- Implementiert: WS-Token-Rotation mit serverseitiger Invalidierung bestehender Verbindungen
- Implementiert: Optionales Admin-Secret (`X-Admin-Secret`) fuer geschuetzte WS-Token-Rotationsaktionen
- Implementiert: Optionales Admin-Secret auch fuer sensible Safety-Steueraktionen (Traffic-Light, Emergency-Release)
- Implementiert: Optionale Admin-Secret-Absicherung fuer Verification-Uploads und zentrale Security-Policy (`docs/SECURITY.md`)
- Implementiert: Session-Timer-APIs fuer Status/Add/Remove/Freeze/Unfreeze inkl. Dashboard-Testkonsole
- Implementiert: Timer-Anzeige im Dashboard ueber WebSocket-`timer_tick`-Events
- Implementiert: Background-Timer-Sweeper (APScheduler) fuer automatisches Session-Ende bei Ablauf
- Implementiert: Aggregierter Session-Verlauf/Event-Log (`GET /api/sessions/{id}/events`) inkl. Dashboard-Abruf
- Implementiert: Session-History-Seite (`/history`) mit Filtern und Export (`/events/export`)
- Implementiert: Vertragsansicht inkl. Addenda und Export (`/contracts`, `/contract/export`)
- Implementiert: Einheitliches API-Fehlerformat + verbessertes UI-Fehlerfeedback (Dashboard/History/Contracts)
- Implementiert: Responsive Mobile-Optimierung fuer Dashboard/History/Contracts (Layout + Controls + Breakpoints)
- Teststatus: `39 passed` (lokale automatisierte Tests)
- Offen: echte KI-Provider-Anbindung, weitergehende Chat-Auth/Identity-Hardening, Browser Push, produktionsnahe UX

---

## Phase 0: Fundament (Woche 1–2)

**Ziel**: Lauffähiges Grundgerüst, Entwicklungsumgebung steht

- [x] Python-Projekt aufsetzen (FastAPI, SQLAlchemy, Alembic)
- [x] SQLite-Datenbank & erstes Schema (Session, Persona, Message, PlayerProfile, Contract)
- [x] Alembic Migrationen einrichten
- [x] Basis-Jinja2-Template mit einfacher CSS-Testoberflaeche
- [ ] HTMX Integration
- [x] `.env`-Konfiguration & Pydantic Settings
- [x] `data/`-Verzeichnis in `.gitignore`
- [ ] Client-Privacy-Baseline: kein LocalStorage, kein IndexedDB, kein Service-Worker-Cache
- [ ] Upload-Pfad für Verifikationsbilder so definieren, dass keine bewusste Galerie-Speicherung durch die App erfolgt

**Deliverable**: `python -m uvicorn app.main:app` startet ohne Fehler

---

## Phase 1: KI-Integration & Chat (Woche 3–4)

**Ziel**: Erste Konversation mit der Keyholderin ist möglich

- [ ] `AIGateway`-Abstraktion implementieren
- [ ] Grok-Provider implementieren (OpenAI SDK kompatibel)
- [ ] Persona-Builder: System-Prompt aus Konfiguration generieren
- [ ] Spieler-Psychogramm modellieren und Onboarding-Fragebogen definieren
- [ ] Player-Profile in den Prompt-Kontext integrieren
- [x] Chat-Router & WebSocket-Verbindung
- [x] Chat-Interface (Jinja2 + JS-Testkonsole inkl. WebSocket-Live-Feed)
- [ ] Persona-Konfigurationsseite
- [ ] Spielerprofil-Konfigurationsseite
- [ ] KI-Konfigurationsseite (API-Key, Modell)
- [ ] API-Key Verschlüsselung (Fernet)

**Deliverable**: Gespräch mit konfigurierter Keyholderin möglich

---

## Phase 2: Session-Mechanik & Timer (Woche 5–6)

**Ziel**: Vollständige Session mit Timer-Logik

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

**Deliverable**: Vollständiger Session-Lifecycle funktioniert

---

## Phase 3: Aufgaben & Belohnungssystem (Woche 7–8)

**Ziel**: KI kann Aufgaben vergeben und Konsequenzen ziehen

- [x] Task-Datenmodell & CRUD
- [ ] KI kann Tasks via Structured Output vergeben
- [x] Task-Anzeige im UI (Aufgabenliste)
- [x] Task als erledigt markieren
- [x] Automatische Konsequenzen bei Failure / Overdue (Lock-Verlaengerung)
- [ ] Psychogramm-gesteuerte Aufgaben- und Straflogik anwenden
- [ ] Belohnungs/Bestrafungs-Events im Verlauf dokumentieren
- [ ] KI-Antworten inkl. Actions-Schema stabil

**Deliverable**: Vollständiges Task & Consequence System

---

## Phase 4: Sicherheitssystem (Woche 9)

**Ziel**: Alle Safety-Features implementiert und zuverlässig

- [x] Ampelsystem (Gelb/Rot API implementiert; UI-Testkonsole vorhanden)
- [ ] Gelb: KI-Prompt-Override für Fürsorge-Modus
- [x] Rot: Session pausieren (API)
- [x] Safeword: sofortiger Session-Stop (API)
- [x] Emergency Release: Pflichtbegründung (API)
- [x] Safety-Log: alle Ereignisse werden gespeichert
- [ ] Safety-Override im System-Prompt verankert

**Deliverable**: Alle Safety-Features vollständig und geprüft

---

## Phase 5: Bildverifikation & Benachrichtigungen (Woche 10–11)

**Ziel**: Verifikation und proaktive Keyholderin

- [x] Bild-Upload-Endpoint (lokal, UUID-Dateiname)
- [ ] KI-Bildanalyse-Integration (Verifikation, aktuell heuristische Stub-Logik)
- [x] Optionale Seal-Nummer in Verifikationsanfrage
- [x] Verifikations-UI (Testkonsole)
- [ ] Hygiene-Öffnungen: Kontingente pro Tag/Woche/Monat implementieren
- [x] Hygiene-Öffnungen: Countdown, Wiederverschluss-Bestätigung und automatische Bestrafung bei Überziehung
- [x] Plomben-Historie: Zerstörung alter Plombe und Pflicht-Eintrag neuer Plombe nach Öffnung
- [x] APScheduler-Basis: periodischer Task-Overdue-Sweep fuer aktive Sessions
- [x] APScheduler: proaktive Keyholderin-Nachrichten
- [ ] Browser Push Notifications (Web Push API)
- [x] Konfigurierbare Benachrichtigungs-Haeufigkeit (Intervall/Cooldown per `.env`)

**Deliverable**: Keyholderin agiert proaktiv, Verifikation funktioniert

---

## Phase 6: Polish & Testing (Woche 12)

**Ziel**: MVP ist produktionsreif für den privaten Einsatz

- [x] Responsive Design (Mobile-Optimierung)
- [x] Error Handling & User Feedback
- [x] Session-History-Seite
- [x] Vertragsansicht inkl. Addenda und Export
- [x] Persona-Bibliothek (mehrere gespeicherte Personas)
- [x] Ollama-Provider implementieren
- [x] Unit/Integration Tests kritischer Services und Flows (Timer, Safety, Contract, Hygiene, Verification)
- [x] Dokumentation finalisieren

**Deliverable**: MVP – vollständig funktionsfähig

---

## Backlog (Post-MVP)

### v1.1 – Qualität & UX
- [ ] Kontext-Window-Management (Session-Zusammenfassungen)
- [ ] Aufgaben-Bibliothek (vordefinierte Tasks pro Persona)
- [ ] Dark Mode
- [ ] Session-Export (als Text/PDF)

### v2.0 – Gamification
- [ ] Achievements / Abzeichen
- [ ] Streak-Tracking
- [ ] Statistiken-Dashboard (Gesamtdauer, Aufgaben-Rate, etc.)
- [ ] Punkte-System

### v3.0 – Remote Keyholder
- [ ] Optionaler Sync-Mechanismus (verschlüsselt, opt-in)
- [ ] Remote-Keyholder-Interface (separater Zugang)
- [ ] Push-Benachrichtigungen für Remote-Keyholder
- [ ] Echtzeit-Kollaboration: Mensch + KI als Co-Keyholder

---

## Priorisierungsmatrix

| Feature | Priorität | Aufwand | Phase |
|---|---|---|---|
| Chat mit Keyholderin | MUSS | Mittel | 1 |
| Spieler-Psychogramm | MUSS | Mittel | 1 |
| Keuschheits-Vertrag | MUSS | Mittel | 2 |
| Timer-Management | MUSS | Mittel | 2 |
| Safety-System | MUSS | Niedrig | 4 |
| Aufgaben-System | MUSS | Mittel | 3 |
| Hygiene-Öffnungen | MUSS | Mittel | 5 |
| Bildverifikation | MUSS | Mittel | 5 |
| Benachrichtigungen | SOLL | Mittel | 5 |
| Gamification | KANN | Hoch | v2.0 |
| Remote-Keyholder | KANN | Sehr hoch | v3.0 |
