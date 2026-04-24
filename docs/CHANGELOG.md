# Changelog – Chastease

Alle nennenswerten Änderungen werden in dieser Datei dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [Unreleased]

## [0.7.0] - 2026-04-24

### Hinzugefuegt

- **Spiel-Feedback-Modus**: Neues Konfigurationsfeld `game_feedback_mode` auf dem Spielstartbildschirm — waehle pro Run zwischen: `Beides` (E-Stim + AI-Sammelreport), `Nur E-Stim`, `Nur AI-Bericht`.
- **Feedback-Modus-Selektor auf Spielstartseite**: Pill-basierte Radiogruppe direkt im Setup-Bereich jeder Spielseite; vorbelegt mit dem globalen Admin-Standard.
- **Datenbankfeld `game_feedback_mode`** in `game_module_settings` inklusive Alembic-Migration (`d4e5f6a7b8c9`).
- **Globale Admin-Voreinstellung** fuer Feedback-Modus in Admin > Spiele-Einstellungen (betrifft alle Spiele als Standard).

### Geaendert

- `StartGameRunRequest` traegt jetzt `game_feedback_mode` (default `both`) — der per-Run gewahlte Modus wird direkt im Run-Summary gespeichert und ueberstimmt die globale Einstellung.
- Spielstartseite (`game_posture.html`) strukturiert mit klaren Abschnitten: Spiel-Parameter · Feedback-Modus · Strafe & Ton.
- Setup-Grid auf 4-spaltig optimiert mit Schwierigkeit als erste Option; responsiv auf 2 Spalten (Tablet) und 1 Spalte (Mobil).
- E-Stim-Calls auf Spielseite (`verify_game_step`, `register_movement_event`, `mark_hold_started`) werden nur noch ausgefuehrt wenn Feedback-Modus E-Stim einschliesst.
- AI-Step-Messages (`game_step_fail`, `game_step_pass`) und Sammelbericht (`game_report`) werden nur noch erstellt wenn Feedback-Modus AI einschliesst.
- `game_started`-Message wird nur noch in AI-Modes erstellt.
- E-Stim-Karte auf der Games-Uebersichtsseite auf Status-only reduziert (Konfigurationslink auf Toys-Seite).

## [0.6.0] - 2026-04-24

### Geaendert

- DB-Feldverschluesselung fuer Session-State und gespeicherte API-Keys temporaer entfernt, damit Alpha-Debugging und Usability-Tests direkt in SQLite moeglich sind.
- Runtime-Start ausserhalb des Dev-Modus verlangt vorerst keinen `CHASTEASE_SECRET_ENCRYPTION_KEY` mehr.
- E-Stim-Anbindung von OTC-WebSocket auf direkte Howl Remote API HTTP-Calls umgestellt.
- Toys- und Admin-Flow nutzen fuer Howl jetzt URL + Access Key (Bearer) statt OTC-Queue/Socket-Lifecycle.
- Event-Dispatch (`continuous`, `fail`, `penalty`, `pass`) sendet Pulse direkt ueber Howl-Endpunkte inklusive optionalem Auto-Stop nach Tick-Dauer.
- Pattern-Defaults fuer Howl harmonisiert (`RELENTLESS`, `CHAOS`, `FASTSLOW`, `CALIBRATION1`, `CALIBRATION2`).

### Hinzugefuegt

- Neues Howl-Client-Modul fuer API-Aufrufe (`/status`, `/set_power`, `/load_activity`, `/start_player`, `/stop_player`).
- Datenbankfeld `howl_access_key` in den OTC/Howl-Settings inklusive Alembic-Migration.
- Primare API-Routen unter `/api/howl/*` mit Legacy-Aliases fuer `/api/otc/*`.
- Neues Access-Key-Eingabefeld in der Toys-Oberflaeche.

### Hinweise

- Dieser Rueckbau ist ausdruecklich temporaer. At-Rest-Verschluesselung fuer Session-State und API-Keys bleibt ein Beta-Blocker und ist in der Roadmap festgehalten.

## [0.5.0] - 2026-03-31

### Hinzugefuegt [0.5.0] - 2026-03-31

- Frontend-Helfer `roleplay_ui.js` fuer gemeinsame Roleplay-/Phasen-Meter in Dashboard und Play.
- Frontend-Helfer `dashboard_session_ui.js` fuer Session-Rahmen, Persona-Auswahl und Profilzusammenfassung im Dashboard.
- Frontend-Helfer `dashboard_roleplay_ui.js` fuer Dashboard-Szene, Beziehungswerte, Phasenfortschritt und Langzeitdynamik.
- Frontend-Helfer `dashboard_hygiene_ui.js` fuer Hygiene-Kontingent und Open/Relock-UI im Dashboard.
- Frontend-Helfer `dashboard_runs_ui.js` fuer Run-History und Run-Report-Rendering im Dashboard.
- Frontend-Helfer `dashboard_safety_ui.js` fuer Hygiene-/Safety-Event-Handling im Dashboard.
- Frontend-Helfer `play_chat_ui.js` fuer Chat-Timeline, Bubble-Rendering und Warnbanner im Play-Modus.
- Frontend-Helfer `play_lovense_ui.js` fuer Toy-Status, Console-Rendering und KI-Plan-Anzeige im Play-Modus.
- Frontend-Helfer `play_lovense_controller.js` fuer Lovense-Bootstrap, Planverarbeitung und Toy-Steuerung im Play-Modus.
- Frontend-Helfer `play_shell_ui.js` fuer wiederverwendbare Dropdown-/Header-Menues im Play-Modus.
- Frontend-Helfer `play_voice_ui.js` fuer Realtime-Voice-Status, Audio-Streaming und Toggle-Verhalten im Play-Modus.
- Frontend-Helfer `play_roleplay_state_ui.js` fuer Szene-, Phasen-, Beziehungs- und Langzeitdynamik-Panel im Play-Modus.
- Frontend-Helfer `play_session_ui.js` fuer Safety-, Hygiene- und Verifikations-Interaktionen im Play-Modus.
- Frontend-Helfer `play_tasks_ui.js` fuer Task-Dropdown, Inline-Action-Cards und Verifikations-Handler im Play-Modus.
- Frontend-Helfer `inventory.js` fuer Import/Export-, Formular- und Inline-Edit-Logik der Inventarverwaltung.
- Frontend-Helfer `personas.js` fuer Persona-Formular, Avatar-Upload, Import/Export und Task-Bibliothek.
- Frontend-Helfer `scenarios.js` fuer Scenario-Presets, Phasen-/Lore-Editor, Import/Export und Inventar-Zuordnung.
- Frontend-Helfer `game_module_settings.js` fuer Spielekonfiguration, Schwellenwerte, Modul-Cards und Masken-Upload.
- Frontend-Helfer `contract_view.js` fuer Markdown-/Tabellen-Rendering der Vertragsdetailseite.
- Frontend-Helfer `profile.js` fuer LLM-/Audio-Tests und Audio-Preset-Aktionen im Wearer-Profil.
- Frontend-Helfer `admin_posture_matrix.js` fuer Filter, Bulk-Aktionen und Vorschau-Modal der Posture-Matrix.
- Frontend-Helfer `game_posture_manage.js` fuer ZIP-Import/Export, Karten-CRUD und Referenz-Skelett-Bearbeitung der Posture-Verwaltung.
- Frontend-Helfer `game_posture.js` fuer Kamera, Pose-/Movement-Analyse, Overlay-Rendering und Run-Steuerung im Live-Spielbildschirm.
- Gemeinsame Frontend-Basis `ui_common.js` und `ui.css` fuer DOM-Helfer, Pill-Listen und wiederkehrende Panel-Muster.
- Gemeinsame Frontend-Runtime `ui_runtime.js` fuer JSON-Requests und Polling-Helper.
- Gemeinsame Format-Helfer in `ui_runtime.js` fuer Datums-, Dauer- und Countdown-Anzeigen.
- Gemeinsame UI-Utilities in `ui.css` fuer `hidden`, `ok` und `warn`.
- Fokusmodus fuer `/play`, der die Sessionflaeche auf Chat, Tasks und Safety reduziert und sekundaere UI-Elemente ausblendet.
- In-Memory-Rate-Limits fuer teure Endpunkte wie Medien-Uploads, Verifikations-Uploads und Voice-Session-Bootstrap.
- Automatische Bereinigung alter Verifikationsbilder per Retention-Job (`CHASTEASE_VERIFICATION_MEDIA_RETENTION_*`).
- Browserorientierter CSRF-Schutz fuer mutierende Requests via Same-Origin-Pruefung und CSRF-Header im Frontend-Basislayout.
- Moderne Passwort-Hashes via `pwdlib` mit Argon2-Backend fuer neue Accounts.
- Login-Migrationspfad: bestehende Legacy-SHA-256-Salt-Hashes werden beim erfolgreichen Login automatisch auf das neue Format umgestellt.
- Erste Lovense-Integration fuer `0.4.0`: serverseitiger Bootstrap fuer das Lovense Standard JS SDK, Dashboard-Panel mit QR-/App-Connect, Toy-Liste und Basisbefehlen fuer Vibrate/Pulse/Wave/Stop.
- Separater Phasen-Session-State (`phase_state_json`) fuer echte Phasenpunkte je Kriterium statt Ableitung aus der Gesamtbeurteilung.
- Scenario-Editor kann Phasen-Zielwerte, Gewichtung und Mindestdauer jetzt direkt pro Phase bearbeiten.
- Alembic-History fuer `0.5.0` erneut auf genau eine frische Initialmigration des aktuellen Schemas zurueckgesetzt.
- Automatische CI-Pipeline fuer `push` und Pull Requests mit Python-Setup, `alembic upgrade head` und vollem `pytest`-Lauf.
- Betriebsdokumentation fuer `0.5.0` inklusive Upgrade-Hinweisen, Backup/Restore, Secret-Handling und Rollback.
- Alpha-Readiness-Dokument mit klaren Release-Grenzen, Blockern und manuellem Smoke-Test.
- Gezielte End-to-End-Smokes fuer einen zentralen Happy Path und einen Safety-Abbruch.

### Geaendert [0.5.0] - 2026-03-31

- Release-Stand auf `0.5.0` angehoben.
- Produktive Defaults gehaertet: `debug` und Play-WS-Debug sind jetzt standardmaessig deaktiviert; ohne `CHASTEASE_SECRET_ENCRYPTION_KEY` startet die App ausserhalb eines expliziten Dev-Modus nicht mehr.
- Rollenlogik fuer `owner`/`admin` zentralisiert, um das spaetere Identity-Konzept sauberer vorzubereiten.
- Auth- und CSRF-Cookies koennen jetzt ueber `CHASTEASE_COOKIE_SECURE` fuer HTTPS-nahe Setups auf `Secure` gesetzt werden.
- Dokumentation (README, Architektur, Security) auf den aktuellen Sicherheits- und Feature-Stand synchronisiert.
- `v0.5` UI-Refactoring gestartet: erste Browserlogik aus `play.js` und `dashboard.js` in wiederverwendbare UI-Helfer ausgelagert.
- `play.js` weiter entkoppelt: die verbleibende Lovense-Steuer- und Planlogik laeuft jetzt ueber einen separaten Controller statt im Seitenskript selbst.
- `play.js` weiter entkoppelt: Safety-, Hygiene- und Verifikationslogik liegen jetzt ebenfalls in einem separaten UI-Helfer; `play.js` ist dadurch unter 1000 Zeilen gefallen.
- Wiederkehrende Pill-/Card-Header-/Warnstil-Muster zwischen Dashboard und Play ueber gemeinsame UI-Klassen und DOM-Helfer zusammengefuehrt.
- `play.js` und `dashboard.js` weiter auf Bootstrapping reduziert: gemeinsame Runtime- und Menu-Helfer uebernehmen Fetch-/Polling- und Dropdown-Standardverhalten.
- Die Inventarverwaltung nutzt keine grosse Inline-Template-Logik mehr, sondern ein eigenes Seitenskript mit denselben gemeinsamen UI-/Runtime-Helfern.
- Die Persona-Verwaltung nutzt ebenfalls kein grosses Inline-Template-Skript mehr, sondern ein eigenes Seitenskript mit denselben gemeinsamen UI-/Runtime-Helfern.
- Die Scenario-Verwaltung nutzt ebenfalls kein grosses Inline-Template-Skript mehr, sondern ein eigenes Seitenskript mit denselben gemeinsamen UI-/Runtime-Helfern.
- Die Spielekonfiguration nutzt ebenfalls kein grosses Inline-Template-Skript mehr, sondern ein eigenes Seitenskript mit denselben gemeinsamen Runtime-Helfern.
- Die Vertragsdetailseite rendert Markdown jetzt ebenfalls ueber ein eigenes Seitenskript statt ueber Inline-JavaScript im Template.
- Das Wearer-Profil nutzt fuer LLM-/Audio-Testaktionen jetzt ebenfalls ein eigenes Seitenskript statt Inline-JavaScript.
- Die Admin-Posture-Matrix nutzt fuer Filter, Bulk-Aktionen und Vorschau jetzt ebenfalls ein eigenes Seitenskript statt Inline-JavaScript.
- Die Posture-Verwaltung nutzt fuer ZIP-Import/Export, Karten-CRUD und Referenz-Skelett-Bearbeitung jetzt ebenfalls ein eigenes Seitenskript statt Inline-JavaScript.
- Der Live-Spielbildschirm nutzt jetzt ebenfalls ein eigenes Seitenskript statt eines grossen Template-Monolithen; im Template bleibt nur noch der Bootstrap fuer Session/Modul/Run-Startwerte.
- Die neuen Frontend-Renderer (`scenarios.js`, `personas.js`, `dashboard_runs_ui.js`, `game_posture.js`) nutzen keine generierten Inline-`onclick`-Handler mehr, sondern delegierte Events.
- Veraltete Lovense-Dashboard-Altlogik entfernt; die Toy-Steuerung liegt jetzt konsistent nur noch im dedizierten Toys-Hub statt doppelt im Dashboard.
- Authentifizierte Seiten verwenden jetzt konsistent dieselbe Hauptnavigation; Landing/Login bleiben bewusst ohne volles App-Menue.
- App-Branding vereinheitlicht: Logo im Header ersetzt den reinen Texttitel und wird auch als Favicon verwendet.
- Dashboard- und Play-Metriken visualisieren jetzt Basiswert, Entwicklung seit Start, naechste Zielphase und Zielmarker direkt auf der Skala.
- Dashboard und Play trennen jetzt langfristige Beziehungsmetriken von kurzfristigem Phasenfortschritt; jede Phase startet mit eigenen Zielwerten wieder bei `0`.
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
- Terminologie im UI vereinheitlicht: `Keyholder-Profile` und `Wearer-Profil` ersetzen die alte Mischung aus `Persona`, `Spielerprofil` und `Setup-Verwaltung`.
- Integrierte System-Keyholder erscheinen jetzt zusammen mit eigenen Keyholder-Profilen in derselben Verwaltung, bleiben dort aber bewusst schreibgeschuetzt.
- Seitenbreiten werden jetzt zentral ueber gemeinsame Layout-Klassen gesteuert statt pro Template mit lokalen `max-width`-Werten.
- Mobile Breakpoints fuer Header und Keyholder-Verwaltung nachgeschaerft, damit Brand-Zeile, Toolbar und Karten auf kleinen Displays wieder sauber umbrechen.
- Roadmap neu geschnitten: Device-/Toy-Fundament priorisiert vor Gamification.
- KI-erzeugte Tasks werden gegen offene, aehnliche Tasks dedupliziert; Fail-/Overdue-Ereignisse bremsen die Phasenprogression wieder korrekt.
- Release-/Deploy-Referenzen auf den umbenannten GitHub-/GHCR-Pfad `amet-titulari/chastesae` ausgerichtet.

### Behoben

- Standalone-Verifikationen crashen nicht mehr bei Roleplay-Fortschritt ohne verknuepften Task.
- Persona- und Scenario-DB-Endpunkte sind wieder konsistent admin-geschuetzt.
- Request-Limits decken jetzt auch Login, Chat-Nachrichten, Verifikationsanforderungen und Push-Test-Dispatch ab.
- Explizite Aufgabenanforderungen im Chat erzeugen jetzt auch bei degradierten LLM-Antworten verlaesslich eine Task-Aktion.

### Upgrade-Hinweise

- GitHub-Repository und GHCR-Image laufen jetzt unter `amet-titulari/chastesae`; lokale Remotes, Portainer-Stacks und externe Pull-Skripte muessen auf den neuen Namen zeigen.
- Beim Upgrade produktiver Instanzen zuerst ein Backup von `data/chastease.db` und `data/media/` erstellen.
- Datenbanken mit aktuellem Schema normal per `alembic upgrade head` migrieren; `alembic stamp head` bleibt nur fuer bereits schema-identische Bestandsdatenbanken gedacht.

## [0.3.5] - 2026-03-25

### Geaendert [0.3.5] - 2026-03-25

- Persona-Stilregeln sind jetzt deutlich staerker persona-gesteuert statt global fest verdrahtet: Formatstil, Ausfuehrlichkeit, Lobstil, Wiederholungsbremse und Kontextsichtbarkeit koennen pro Persona festgelegt sowie importiert/exportiert werden.
- Chat rendert jetzt leichtes Markdown in Nachrichten (`**fett**`, `*kursiv*`, `` `code` `` und Zeilenumbrueche), waehrend Klartext-Personas weiterhin von rohen Markdown-Markern bereinigt werden.
- Ametara Titulari wurde auf kuerzere, klarere und weniger wiederholende Antworten mit dezentem Markdown, staerkerer Wiederholungsbremse und minimalerer Meta-Rezitation neu abgestimmt.

### Hinzugefuegt [0.3.5] - 2026-03-25

- Neue Persona-Felder und Migration fuer `formatting_style`, `verbosity_style`, `praise_style`, `repetition_guard` und `context_exposition_style`.

## [0.3.4] - 2026-03-23

### Geaendert [0.3.4] - 2026-03-23

- Eingebrannte Verifikations-Overlays auf Bildern deutlich lesbarer gemacht: groessere Typografie, staerkerer Kontrast, Mindestbreite fuer Top-Boxen sowie kraeftigere Kontur und Hintergrund fuer Chat- und Game-Verifikationen.
- Test-Artefakte von Runtime-Daten getrennt: SQLite-Testdatenbank, Test-Medien und Audit-Logs laufen jetzt unter `data-tests/`, waehrend `data/` fuer echte App-Daten reserviert bleibt.

### Tests

- Overlay-Rendering mit zusaetzlichem Unit-Test fuer Mindestbreite der Burn-in-Boxen abgesichert.

## [0.2.7] - 2026-03-16

### Geaendert [0.2.7] - 2026-03-16

- Spiel-Schwellwerte fuer `dont_move` neu kalibriert: Balanced als neuer Default mit hoeheren Toleranzgrenzen.
- Preset-Logik fuer Schwellwerte auf feste Vorschlagwerte pro Button (`Tolerant`, `Balanced`, `Strict`) zurueckgestellt.
- Preset-Abstufung fuer `dont_move` vereinheitlicht: `Tolerant` = 25% einfacher als Balanced, `Strict` = 25% schwieriger als Balanced.
- Standard-Multiplikatoren fuer neue Moduleinstellungen angepasst (`easy` 0.75, `hard` 1.50).

---

## [0.2.5] - 2026-03-15

### Hinzugefuegt [0.2.5] - 2026-03-15

- Drittes Spielemodul `tiptoeing` ("Auf Zehenspitzen stehen") als Single-Pose-Stillhalte-Spiel mit AI-Verifikation.
- Modul in Registry und Module-Listing integriert.

### Geaendert [0.2.5] - 2026-03-15

- Single-Pose-Strict-Laufzeitlogik aus `dont_move` generalisiert, damit mehrere Module dieselbe strenge Verifizierungsmechanik nutzen koennen.
- Game-Frontend (`/game/{session_id}`) auf modulklassenbasierte Single-Pose-Logik erweitert (Auswahl, Startparameter, Monitoring).

### Tests [0.2.5] - 2026-03-15

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

### Geändert [0.2.2] – 2026-03-14

- Dokumentation vollständig mit aktuellem Systemstand synchronisiert (ARCHITECTURE, CHANGELOG, ROADMAP, BENUTZERANLEITUNG, SECURITY).

---

## [0.2.1] – 2026-03-14

### Hinzugefügt [0.2.1] – 2026-03-14

- Task-Nummer (#ID) in allen Action Cards und im Tasks-Dropdown sichtbar.
- Deadline-Anzeige rechtsbündig in der Card-Titelzeile (mit Farbcodierung: normal/bald/überfällig).
- Tasks-Dropdown zeigt jetzt interaktive Action Cards statt read-only Liste.
- Persona-Avatar neben KI-Nachrichten im Chat (wenn Avatar in Persona hinterlegt).

### Geändert [0.2.1] – 2026-03-14

- Dropdown-Breite auf 360 px erhöht für bessere Lesbarkeit der Action Cards.
- Buttons kontextabhängig: Bestätigung + Fail (ohne Verifikation) oder Fotoverifikation + Fail (mit Verifikation).

### Behoben [0.2.1] – 2026-03-14

- UTC-Fix: SQLite-naive Datetimes werden vor Serialisierung explizit als UTC markiert – Deadline-Zeiten werden im Browser korrekt in Lokalzeit angezeigt.
- `deadline_at`-Serialisierung auf `.isoformat()` umgestellt (statt `str()`) für zuverlässiges Browser-Parsing.

---

## [0.2.0] – 2026-03-13

### Geändert [0.2.0] – 2026-03-13

- Experience-Onboarding schreibt Werte bei Navigation direkt als Defaults und in die aktive Session.
- Terminologie in der UI vereinheitlicht: "Persona" in zentralen Onboarding-Stellen zu "Keyholderin" geändert.
- Scenario-Verwaltung von Persona-Verknüpfung entkoppelt; Scenarios erzwingen keine Keyholderin mehr.
- Hygiene-Regelanzeige im Play-Drawer vereinfacht und auf Regeln aus Session/Profil abgestimmt.
- Penalty-Felder in Experience klarer benannt ("Wert" + gemeinsame Einheit) inkl. Doku-Hinweis.

### Behoben [0.2.0] – 2026-03-13

- Logik-/UI-Irritationen bei Scenario↔Persona-Verknüpfung im Onboarding.
- Inkonsistenzen bei der Übernahme von Experience-Änderungen in laufende Sessions.

---

## [0.1.0] – 2025-01-27

Erste öffentliche Alpha-Version mit vollständigem Feature-Set für Solo-Nutzung im Heimnetz.

### Hinzugefügt [0.1.0] – 2025-01-27

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
