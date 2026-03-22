# Changelog – Chastease

Alle nennenswerten Änderungen werden in dieser Datei dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [Unreleased]

### Hinzugefuegt

- Browserorientierter CSRF-Schutz fuer mutierende Requests via Same-Origin-Pruefung und CSRF-Header im Frontend-Basislayout.
- Moderne Passwort-Hashes via `pwdlib` mit Argon2-Backend fuer neue Accounts.
- Login-Migrationspfad: bestehende Legacy-SHA-256-Salt-Hashes werden beim erfolgreichen Login automatisch auf das neue Format umgestellt.

### Geaendert

- Auth- und CSRF-Cookies koennen jetzt ueber `CHASTEASE_COOKIE_SECURE` fuer HTTPS-nahe Setups auf `Secure` gesetzt werden.
- Dokumentation (README, Architektur, Security) auf den aktuellen Sicherheits- und Feature-Stand synchronisiert.
- Authentifizierte Seiten verwenden jetzt konsistent dieselbe Hauptnavigation; Landing/Login bleiben bewusst ohne volles App-Menue.
- App-Branding vereinheitlicht: Logo im Header ersetzt den reinen Texttitel und wird auch als Favicon verwendet.
- Dashboard- und Play-Metriken visualisieren jetzt Basiswert, Entwicklung seit Start, naechste Zielphase und Zielmarker direkt auf der Skala.
- Resistance wird in der Fortschrittsanzeige als negative Entwicklung dargestellt; fallende Werte werden rot markiert und als `Punkte weniger` beschrieben.
- Chat-Antworten koennen Roleplay-State-Aenderungen jetzt notfalls aus freiem Antworttext ableiten, wenn die KI keine strukturierte `update_roleplay_state`-Action mitsendet.
- Chat-Fehler beim Nachrichtensenden werden serverseitig abgefangen und als sichtbare System-/Fallback-Antwort protokolliert statt als roher 500er im Frontend zu enden.
- Chat-Verifikationen verwenden jetzt das Dateinamensschema `session<id>-chat-task<task_or_verification_id>-<timestamp>.<ext>`.
- Safety-Ampel (`traffic-light`) ist jetzt eine Owner-Aktion ohne zusaetzliches Admin-Secret; nur `emergency-release` und WS-Token-Rotation bleiben Admin-geschuetzt.
- `Don't move`-Livevorschau vereinfacht: störende Overlay-Boxen entfernt, farbiger Rahmen beibehalten, Skelett nur noch rot/grün.
- Kontrollbild-Annotationen fuer Bewegungsverstösse lesbarer gemacht, inkl. groesserer Label-Schrift im Frontend-Fallback und serverseitig eingebrannten Bildern.
- Spielekonfiguration entschlackt: ungenutzte Zeilen `Default Werte` und `Empfehlung` aus der modulspezifischen Schwellenwert-UI entfernt.
- Session-Start zieht bei gesetzter Mindest- und Maximaldauer jetzt konsistent eine tatsächliche Laufzeit innerhalb der gewählten Spanne statt immer nur die Mindestdauer zu verwenden.
- Neue Sessions aus abgeschlossenen Vorlagen starten mit frischem Roleplay-State statt alte Szenen-, Beziehungs- und Protokollzustände blind zu übernehmen.
- Chat markiert degradierten AI-Betrieb jetzt sichtbar bei Providerfehlern statt still auf generische Echo-Antworten zurückzufallen.
- Proaktive Reminder nutzen jetzt Persona-, Szenen- und Protokollkontext statt starre Standardtexte.
- Addenda fuer aktive Sessions klemmen laufende Dauer jetzt gezielt in den neuen Min/Max-Rahmen, statt implizit auf die reine Mindestdauer zurückzufallen.
- Vertrags-Addenda sind jetzt auf klar definierte Vertrags- und Policy-Felder erweitert: `min/max`, Hygiene-Limits, maximale Hygiene-Oeffnungsdauer, Penalty-Parameter sowie aktive Regeln und offene Anweisungen.
- Vertrags-Addenda validieren und klassifizieren Aenderungen jetzt mit `standard`/`high_impact`-Consent-Stufe und liefern strukturierte Wirkungsmetadaten fuer UI und Export.
- Vertrags-Addenda manipulieren die verbleibende Restzeit nicht direkt mehr; diese bleibt bewusst task- und ereignisgesteuert ausserhalb des Vertrags.
- Vertrags-Onboarding und Contract-Preview fuehren jetzt strukturierte Vertragsfelder fuer Ziel, Methode, Trageweise, Beruehrungs-/Orgasmusregeln, Belohnungen und Widerruf statt nur freier AI-Ausformulierung.
- Persona- und Scenario-Verwaltung ist im Onboarding nicht mehr nur Auswahl, sondern auch direktes Anlegen, Bearbeiten und Speichern fuer normale Nutzer.
- Hauptnavigation und Session-UX neu getrennt: `Experience` ist in der Navigation jetzt `Chat`, waehrend ein neues Spieler-Dashboard Sessionrahmen, Einstimmung, Hygiene/Safety und Spielresultate zentral buendelt.
- Chat-Header in `/play` stark entschlackt: `Verbleibend`, `Einstimmung`, `Regenerate`, `Verlauf` und der Settings-Drawer sind aus der Gespraechsflaeche entfernt und ins Dashboard ausgelagert.
- Spielverlauf und Resultate sind nicht mehr in der Games-Uebersicht verteilt, sondern pro Session gesammelt im Dashboard sichtbar.
- Play-Mode zeigt degradierte AI-/Reminder-Zustände jetzt zusätzlich sichtbar als Banner im UI.
- Experience-Onboarding bietet jetzt einen Quick-Start-Pfad fuer Solo-Sessions mit reduzierter Vorkonfiguration.
- Chat-Kontext fuehrt jetzt einen kompakten Session-Memory-Block plus expliziten Roleplay-Status fuer stabilere narrative Kontinuität.

## [0.2.7] - 2026-03-16

### Geaendert

- Spiel-Schwellwerte fuer `dont_move` neu kalibriert: Balanced als neuer Default mit hoeheren Toleranzgrenzen.
- Preset-Logik fuer Schwellwerte auf feste Vorschlagwerte pro Button (`Tolerant`, `Balanced`, `Strict`) zurueckgestellt.
- Preset-Abstufung fuer `dont_move` vereinheitlicht: `Tolerant` = 25% einfacher als Balanced, `Strict` = 25% schwieriger als Balanced.
- Standard-Multiplikatoren fuer neue Moduleinstellungen angepasst (`easy` 0.75, `hard` 1.50).

---

## [0.2.5] - 2026-03-15

### Hinzugefuegt

- Drittes Spielemodul `tiptoeing` ("Auf Zehenspitzen stehen") als Single-Pose-Stillhalte-Spiel mit AI-Verifikation.
- Modul in Registry und Module-Listing integriert.

### Geaendert

- Single-Pose-Strict-Laufzeitlogik aus `dont_move` generalisiert, damit mehrere Module dieselbe strenge Verifizierungsmechanik nutzen koennen.
- Game-Frontend (`/game/{session_id}`) auf modulklassenbasierte Single-Pose-Logik erweitert (Auswahl, Startparameter, Monitoring).

### Tests

- Games-Flow-Tests fuer Modul-Listing und Start-Flow von `tiptoeing` ergaenzt.

---

## [0.2.3] – 2026-03-14

### Hinzugefügt

- Modulares Spiele-Framework (Registry + Module-Definition) als Basis fuer weitere Spielmodule.
- Erste Spiele-Erweiterung `posture_training` mit Schwierigkeitsgraden (`easy`, `medium`, `hard`).
- Persistente Runtime-Tabellen fuer Spiele: `game_runs`, `game_run_steps`.
- Games-API-Endpunkte fuer Module, Run-Start, Run-Status und Step-Verifikation mit Bild-Upload.
- Retry-Mechanik: fehlgeschlagene Posture wird ans Spielende eingehaengt und erhoeht die Gesamtspielzeit variabel je nach Schwierigkeit.
- Max-Miss-Regel mit konfigurierbarer Session-Penalty (Lock-End-Verlaengerung).
- Abschlussbericht als `game_report`-Systemevent zur Bewertung weiterer Session-Penalties.
- Neuer Game-UI-Screen `/game/{session_id}` mit Gesamt-Timer, Posture-Anzeige und Auto-Capture (Laptop-Cam via `getUserMedia`).

### Geändert

- Roadmap auf v0.2.3 aktualisiert und Spiele-Erweiterung als aktiv gestartet markiert.

---

## [0.2.2] – 2026-03-14

### Geändert

- Dokumentation vollständig mit aktuellem Systemstand synchronisiert (ARCHITECTURE, CHANGELOG, ROADMAP, BENUTZERANLEITUNG, SECURITY).

---

## [0.2.1] – 2026-03-14

### Hinzugefügt

- Task-Nummer (#ID) in allen Action Cards und im Tasks-Dropdown sichtbar.
- Deadline-Anzeige rechtsbündig in der Card-Titelzeile (mit Farbcodierung: normal/bald/überfällig).
- Tasks-Dropdown zeigt jetzt interaktive Action Cards statt read-only Liste.
- Persona-Avatar neben KI-Nachrichten im Chat (wenn Avatar in Persona hinterlegt).

### Geändert

- Dropdown-Breite auf 360 px erhöht für bessere Lesbarkeit der Action Cards.
- Buttons kontextabhängig: Bestätigung + Fail (ohne Verifikation) oder Fotoverifikation + Fail (mit Verifikation).

### Behoben

- UTC-Fix: SQLite-naive Datetimes werden vor Serialisierung explizit als UTC markiert – Deadline-Zeiten werden im Browser korrekt in Lokalzeit angezeigt.
- `deadline_at`-Serialisierung auf `.isoformat()` umgestellt (statt `str()`) für zuverlässiges Browser-Parsing.

---

## [0.2.0] – 2026-03-13

### Geändert

- Experience-Onboarding schreibt Werte bei Navigation direkt als Defaults und in die aktive Session.
- Terminologie in der UI vereinheitlicht: "Persona" in zentralen Onboarding-Stellen zu "Keyholderin" geändert.
- Scenario-Verwaltung von Persona-Verknüpfung entkoppelt; Scenarios erzwingen keine Keyholderin mehr.
- Hygiene-Regelanzeige im Play-Drawer vereinfacht und auf Regeln aus Session/Profil abgestimmt.
- Penalty-Felder in Experience klarer benannt ("Wert" + gemeinsame Einheit) inkl. Doku-Hinweis.

### Behoben

- Logik-/UI-Irritationen bei Scenario↔Persona-Verknüpfung im Onboarding.
- Inkonsistenzen bei der Übernahme von Experience-Änderungen in laufende Sessions.

---

## [0.1.0] – 2025-01-27

Erste öffentliche Alpha-Version mit vollständigem Feature-Set für Solo-Nutzung im Heimnetz.

### Hinzugefügt

#### Core-Session-Mechanik
- Session-Lifecycle: Erstellen, Starten, Beenden, Timer-Management (hinzufügen, entfernen, einfrieren)
- Digitaler Vertrag mit Addenda und Consent-Workflow
- Session-Event-Log mit PDF- und JSON-Export
- APScheduler-Hintergrundjobs: Task-Overdue-Sweep, Timer-Ablauf-Sweep, proaktive Nachrichten

#### KI-Keyholderin
- Abstraktionsschicht für KI-Provider: `CustomOpenAI` (xAI/Grok-kompatibel), `Ollama`, `Stub`
- Anpassbare Persona-Profile mit individuellen Charakterzügen und Presets
- System-Prompt enthält Grenzen (`wearer_boundary`), Stil, Ziel und aktive Tasks
- Structured-Output-Actions: `create_task`, `add_time`, `fail_task`
- `normalize_actions()`: Validierung und Normalisierung aller KI-Actions; robuste Fallbacks bei fehlerhaftem JSON
- Offene Tasks werden als Kontext-Block in jeden Chat-Request injiziert

#### Aufgaben-System
- Task-Modell mit `title`, `description`, `requires_verification`, `verification_criteria`, `consequence_type`/`value`
- Status-Maschine: `pending` → `completed` / `failed`
- Konsequenzen: Zeitstrafe (`add_time`) oder Zeitbonus (`remove_time`) bei Task-Abschluss
- Task-Events: `task_reward`, `task_penalty`, `task_failed` im Session-Event-Log
- `fail_task`-Action: KI kann Tasks direkt als fehlgeschlagen markieren

#### Bildverifikation
- Verifikations-Request mit erwarteter Plomben-Nummer
- Foto-Upload direkt in der Aktionskarte (inline, kein Seitenwechsel)
- KI-gestützte Bildanalyse (Plomben-Nummer-Erkennung)
- Ergebnis (bestätigt/abgelehnt) im Chat und in der Aktionskarte
- Seal-History-Protokollierung

#### Sicherheitssystem
- Ampelsystem (Grün/Gelb/Rot) mit Safety-Log
- Safeword-Auslösung
- Notfallentlassung (Emergency Release)
- Safety-Override im Chat: Gelb → fürsorglich-sorgender Ton; Rot → Session pausiert, KI deeskaliert

#### Hygiene-Öffnungen
- Zeitlich begrenzte Entsperrung mit Kontingent-Management
- Relock-Funktion (manuell oder automatisch bei Timer-Ablauf)
- Protokollierung aller Öffnungen

#### Web-UI (Jinja2 + Vanilla JS)
- Play-Ansicht (`/play`): Single-Column-Layout, vollständig responsive (`100dvh`)
- **Aktionskarten** inline in der Chat-Timeline (kein separates Panel)
  - Pro offenem Task eine Karte mit Buttons „Erledigt", „Fehlgeschlagen", „Verifizieren"
  - Verifikation läuft komplett inline in der Karte ab
- Task-Dropdown im Header (read-only Übersicht) mit rotem Badge-Counter
- Settings-Drawer: Session-Info, Hygiene, Ampel, Safeword, Notfall, Persona-Wechsel
- Dashboard (`/`), Session History (`/history`), Contracts (`/contracts`)
- Web Push: Browser-Subscriptions, Benachrichtigungen

#### Authentifizierung & Multi-Device
- Benutzerregistrierung und Login mit bcrypt-Passwort-Hashing
- Dauerhaftes Session-Token (30 Tage, httpOnly-Cookie)
- Multi-Device-Support: Login regeneriert Token **nicht**, wenn bereits eines existiert – kein gegenseitiges Ausloggen

### Geändert / Behoben

- **Seal-Anzeige**: `sealData.items` → `sealData.entries` in play.js (Verifikationsdetails wurden nicht angezeigt)
- **Multi-Device-Logout**: Login generierte stets ein neues Token → behoben, Token bleibt erhalten
- **fail_task-Action**: Fehlte vollständig in Normalizer, Prompt und Backend-Handler → komplett implementiert
- **Boundary im AI-Kontext**: `wearer_boundary` wurde nicht in den KI-Prompt übertragen → Fallback-Chain aus `PlayerProfile.preferences_json` und `AuthUser.setup_boundary` implementiert
- **Action-Karten-Position**: Karten erschienen unterhalb des Eingabefeldes → in Chat-Timeline verschoben
- **Mobile Layouts**: Kompakter Header, `100dvh`, scrollbare Chat-Timeline, versteckte unwichtige Labels auf kleinen Screens

### Entfernt

- Aside-Panel in der Play-Ansicht (Task-Board als separate Sidebar) → ersetzt durch inline Aktionskarten
- Separater `#play-action-cards`-Container → Karten jetzt direkt in `chatTimeline`

---

*Ältere Entwicklungs-Commits vor v0.1.0 sind im Git-Log dokumentiert.*
