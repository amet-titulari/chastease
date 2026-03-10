# Roadmap – Chastease

## Entwicklungsphasen

## Stand (Alpha)

- Implementiert: FastAPI-Grundgeruest, SQLAlchemy-Modelle, Alembic-Migrationen `0001`-`0003`, Session/Contract/Hygiene/Safety/Verification APIs
- Implementiert: Interaktive Web Test Console im Dashboard fuer manuelle End-to-End-Tests
- Teststatus: `12 passed` (lokale automatisierte Tests)
- Offen: echte KI-Provider-Anbindung, Chat/WebSocket, Aufgaben-System, Notifications, produktionsnahe UX

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
- [ ] Chat-Router & WebSocket-Verbindung
- [ ] Chat-Interface (Jinja2 + HTMX)
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
- [ ] Timer-Service: läuft im Background via APScheduler
- [ ] Timer-Operationen: add/remove/freeze/unfreeze
- [ ] Timer-Anzeige im Dashboard (WebSocket-Updates)
- [x] Session-Status-Maschine (active / paused / emergency/safeword/pause)
- [ ] Session-Verlauf / Event-Log
- [ ] Session regulär beenden

**Deliverable**: Vollständiger Session-Lifecycle funktioniert

---

## Phase 3: Aufgaben & Belohnungssystem (Woche 7–8)

**Ziel**: KI kann Aufgaben vergeben und Konsequenzen ziehen

- [ ] Task-Datenmodell & CRUD
- [ ] KI kann Tasks via Structured Output vergeben
- [ ] Task-Anzeige im UI (Aufgabenliste)
- [ ] Task als erledigt markieren (mit optionalem Kommentar)
- [ ] Automatische Konsequenzen bei Completion / Failure
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
- [ ] APScheduler: proaktive Keyholderin-Nachrichten
- [ ] Browser Push Notifications (Web Push API)
- [ ] Konfigurierbare Benachrichtigungs-Häufigkeit

**Deliverable**: Keyholderin agiert proaktiv, Verifikation funktioniert

---

## Phase 6: Polish & Testing (Woche 12)

**Ziel**: MVP ist produktionsreif für den privaten Einsatz

- [ ] Responsive Design (Mobile-Optimierung)
- [ ] Error Handling & User Feedback
- [ ] Session-History-Seite
- [ ] Vertragsansicht inkl. Addenda und Export
- [ ] Persona-Bibliothek (mehrere gespeicherte Personas)
- [ ] Ollama-Provider implementieren
- [x] Unit/Integration Tests kritischer Services und Flows (Timer, Safety, Contract, Hygiene, Verification)
- [ ] Dokumentation finalisieren

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
