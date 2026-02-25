# SRS - Anforderungen (MVP)

## 1. Rollen und Grundlogik

- Rolle `Wearer`:
  - startet und spielt eine Session
  - interagiert per Chat
  - hat ausser Chat keinen direkten Ausfuehrungszugriff auf Keyholder-Aktionen
- Rolle `Keyholder`:
  - wird durch KI repraesentiert
  - steuert die Sitzung innerhalb der Session-Policy
- Session-Regel:
  - jeder Wearer hat genau eine aktive Session gleichzeitig

## 2. Session-Lifecycle

Zustaende:
- `draft`
- `setup_in_progress`
- `configured`
- `active`
- `paused`
- `ended`
- `archived`

Ablauf:
1. Wearer startet neue Session.
2. System erstellt/haelt eine Setup-Session im Status `draft`.
3. Setup-Agent stellt Konfigurationsfragen und wechselt auf `setup_in_progress`.
4. Setup-Agent erhebt zusaetzlich psychologische Neigungen (consent-basiert) und erzeugt ein Psychogramm.
5. System erzeugt verbindliche Session-Policy inkl. Psychogramm-Snapshot.
6. Wearer bestaetigt `Complete Setup`; Setup-Status wechselt auf `configured`.
7. Nach `configured` sind Setup-Aenderungen gesperrt (Start-Setup, Psychogramm, AI-Config, Complete Setup).
8. Session wechselt auf `active`.
9. Keyholder (KI) fuehrt Chat + Aktionen policy-konform aus.

Setup-Lock-Regel:
- Nach bestaetigtem `Complete Setup` sind Konfigurationsaenderungen unterbunden.
- `AI Chat`, `Psychogram Brief` und `Response` bleiben fuer Analyse/Test zugreifbar.

## 3. Setup-Agent und Session-Policy

Der Setup-Agent muss folgende Konfiguration erheben:

- Sicherheitsmodus:
  - Hard-Stop `enabled` oder `disabled` (durch Wearer waehlbar)
- Autonomiegrad:
  - `execute` (default) oder `suggest`
- KI-Charakterprofil:
  - Wesenszuege/Tonfall/Strengegrad/Interaktionsstil
- Psychologischer Fragebogen:
  - BDSM-test-aehnlicher, consent-basierter Fragenkatalog
  - Ermittlung von Vorlieben, Grenzen, Triggern, Belastungsrahmen
  - Umfang fuer MVP: kurzer Einstiegsfragebogen mit ca. 8-12 Fragen (Skala 1-10)
  - Erstellung eines kompakten Psychogramms als Kontextprofil fuer den KI-Keyholder
  - Ziel: KI versteht Vorlieben/Abneigungen besser und gestaltet Interaktion/Verlauf interessanter
  - Psychogramm ist dynamisch aktualisierbar (`updated_at`, `update_reason`)
- Sitzungsgrenzen:
  - Zeitrahmen, Straff- und Gutschriftgrenzen, Oeffnungsregeln
- Bildkontrolle:
  - KI entscheidet Zeitpunkt der Kontrolle
  - Policy definiert Rahmenbedingungen (z. B. "kein Gesicht sichtbar", Beurteilungskriterien)
- Integrationen:
  - Integrationen sind benutzerwaehlbar und nicht zwingend
  - mehrere Integrationen duerfen parallel aktiv sein (z. B. Chaster und Emlalock gleichzeitig)
  - Setup-Agent erstellt Sessions bei Chaster/Emlalock soweit durch API unterstuetzt automatisch

Anforderung an Datennutzung:
- Fragebogenantworten und Psychogramm duerfen ausschliesslich fuer Sessionsteuerung, Sicherheit und KI-Profilschaerfung verwendet werden.
- Das Psychogramm dient als Interaktionsprofil, nicht als klinische Diagnostik.
- Schema und Ableitungsregeln:
  - `docs/architecture/PSYCHOGRAM_SCHEMA.md`
- Trigger-/Filter-Anforderung:
  - `blocked_trigger_words` und `forbidden_topics` muessen in Policy-Sicherheitsfilter einfliessen.

## 4. Aktionsmodell (Keyholder)

Beispielaktionen:
- Hygieneoeffnung
- Timer pausieren (`pause_timer`)
- Timer fortsetzen (`unpause_timer`)
- Zeit zur Endzeit addieren (`add_time`)
- Zeit von der Endzeit abziehen (`reduce_time`)
- Sitzungseinstellungen aendern (`update_session_settings`)
- Kontrollbild anfordern
- Kontrollbild pruefen und bewerten
- Chaster/Emlalock-Aktion ausfuehren
- TTLock-Schluesseltresor steuern

Regeln:
- Alle Aktionen laufen ueber Policy-Pruefung.
- Fuer TTLock-Oeffnen/Schliessen gilt 2-Phasenfreigabe.
- Im Modus `suggest` werden Aktionen vorgeschlagen, nicht sofort ausgefuehrt.
- Phase 2 der TTLock-Freigabe bestaetigt der Wearer selbst.
- Missachtungen von Oeffnungsdauern werden als Policy-Verstoss im Audit protokolliert und duerfen Folgeaktionen ausloesen.
- Bei `confidence < 0.5` muessen konservative Defaults aktiv werden:
  - `tone=balanced`
  - `max_intensity_level=2`
  - `autonomy_profile=suggest_first`
  - `autonomy_bias=80`
  - `max_penalty_per_day_minutes=20`

### 4.1 Timer- und Endzeit-Semantik (verbindlich)

Timer-Grundlage:
- In jeder aktiven Session existieren mindestens:
  - `start_time`
  - `contract_min_end_time`
  - `current_end_time`
- Ein Countdown laeuft auf Basis von `current_end_time` rueckwaerts.

Aktion `pause_timer`:
- stoppt den Countdown sofort.
- Session-Status wechselt auf `paused`.
- Waehrend Pause bleibt `contract_min_end_time` unveraendert.
- Solange pausiert ist, gilt `current_end_time` als vorlaeufig (nicht finalisiert) und wird bei Resume korrigiert.

Aktion `unpause_timer`:
- setzt den Countdown fort.
- Session-Status wechselt auf `active`.
- Die gesamte Pausendauer seit `pause_timer` wird auf `current_end_time` addiert.
- Dadurch wird die neue Endzeit fixiert und der Countdown laeuft von dort weiter.

Aktion `add_time`:
- erhoeht `current_end_time` um die angeforderte Dauer (z. B. Minuten).
- ist in `active` und `paused` erlaubt.
- muss Policy-Limits (z. B. max. Penalty pro Tag/Woche) einhalten.
- API-Kanonik: Backend verarbeitet intern immer `seconds`.
- Eingabe erlaubt:
  - direkt `seconds`
  - oder `amount` + `unit` (`seconds|minutes|hours|days`), welches serverseitig nach Sekunden normalisiert wird.

Aktion `reduce_time`:
- reduziert `current_end_time` um die angeforderte Dauer.
- ist in `active` und `paused` erlaubt.
- darf nie unter `contract_min_end_time` reduzieren.
- API-Kanonik: Backend verarbeitet intern immer `seconds`.
- Eingabe erlaubt:
  - direkt `seconds`
  - oder `amount` + `unit` (`seconds|minutes|hours|days`), welches serverseitig nach Sekunden normalisiert wird.

Aktion `update_session_settings`:
- erlaubt autonome Aenderungen durch die KI an freigegebenen Sessionparametern.
- die KI entscheidet selbststaendig, ob und wann Aenderungen erforderlich sind.
- Aenderungen muessen gegen Policy validiert und auditierbar persistiert werden.
- Sperrregeln fuer Setup-Lock bleiben unveraendert (kein Ruecksprung in Setup-Konfiguration).

Erlaubte Felder fuer `update_session_settings`:
- Psychogramm-nahe Felder, z. B. Interaktionsstil/Tonfall/Eskalationssteuerung innerhalb definierter Policy-Grenzen.
- Sessionvorgaben ohne Sicherheitskritikalitaet, z. B. Kontrollfrequenz-Hinweise, reward/penalty-Feintuning innerhalb vorhandener Caps.

Explizit verbotene Felder fuer `update_session_settings`:
- `contract_max_end_date` (Max-Enddatum)
- `safety_mode`
- `safeword`
- `traffic_light_words` (Ampelsystem)

Zusatzregel:
- Sicherheitsrelevante Parameter duerfen nicht durch KI-Aktion geaendert werden; sie bleiben nur durch expliziten Wearer-Setup-Pfad aenderbar.

## 5. Bildverarbeitung

- Ziel: automatische Beurteilung bevorzugt.
- Beurteilung basiert auf:
  - Session-Policy
  - KI-Charakterprofil
  - Wearer-Wuenschen
- Speicherung:
  - Bilder verschluesselt ablegen (Verschluesselung verpflichtend)
  - Loeschen waehrend aktiver Session nicht erlaubt
  - bei Session-Ende: Entscheidung `loeschen` oder `archivieren`

## 6. Integrationen und Umgebungen

- Zielintegrationen:
  - TTLock (stark empfohlen)
  - Chaster (optional)
  - Emlalock (optional)
  - gleichzeitige Parallel-Integration ist zulaessig
- Testbarkeit:
  - Sandbox/Testumgebung fuer alle Integrationen
  - reproduzierbare Testfaelle fuer kontinuierliche Weiterentwicklung

## 7. Sicherheit, Audit, Export, Recovery

- Auth:
  - Mindestanforderung: Benutzername/Passwort
  - MVP-Stand: API-Auth-Token werden serverseitig in-memory gehalten (kein persistentes AuthSession-Model)
  - Folge: nach Server-Neustart ist erneuter Login erforderlich
  - Ziel: Passkey (WebAuthn) als bevorzugte starke Option
  - optional: OAuth als spaetere Erweiterung
  - JWT Access/Refresh als spaetere Erweiterung
- Mandantenfaehigkeit:
  - fuer MVP nicht erforderlich
- Audit:
  - lueckenloses Audit-Protokoll von KI-Entscheidungen und ausgefuehrten Aktionen ist verpflichtend
- Export:
  - strukturierter Export von Session-, Turn- und Auditdaten
  - bevorzugte Formate: JSON und signierter PDF-Bericht
- Backup/Recovery:
  - Backup-Mechanismus erforderlich
  - AI-Memory-Protokoll, um nach Abbruch den Verlauf stichwortartig wiederherzustellen

## 8. Nicht-funktionale Anforderungen

- Zuverlaessigkeit:
  - idempotente Aktionsausfuehrung bei Integrationen
  - Retries mit klaren Grenzen
- Performance:
  - Hauptfokus auf niedriger Latenz fuer Chat-Interaktion Wearer <-> Keyholder
  - Agenten-/Aktionsmodus darf hoehere Latenz haben als Chatmodus
- Sicherheit:
  - verschluesselte Datenspeicherung sensibler Inhalte
  - minimale Datenhaltung und klare Retention-Regeln
- Nachvollziehbarkeit:
  - KI-Aktionen muessen nicht immer begruendbar sein, aber immer auditierbar

## 9. Betriebs- und Deploymentanforderungen

- Zielarchitektur als Docker-Stack
- horizontal skalierbar (mehrere API-Instanzen)
- zustandslose API-Container; Zustand in Datenbank/externen Services

## 10. UI/UX Anforderungen

- Das Frontend muss modern, responsive und geraeteuebergreifend nutzbar sein.
- Mehrsprachigkeit ist verpflichtend: Deutsch (`de`) und Englisch (`en`) fuer MVP.
- Ein Wearer muss Sessions nahtlos zwischen Smartphone, Tablet und Desktop fortsetzen koennen.
- Chat steht im UX-Fokus und muss auf Mobile priorisiert dargestellt werden.
- Kritische Aktionen muessen mit klarer, fehlersicherer Nutzerfuehrung dargestellt werden.
- Cross-Device-Zustand (letzter Turn, Sessionstatus) muss konsistent synchronisiert sein.
- Siehe Detailanforderungen:
  - `docs/UI_UX_REQUIREMENTS.md`

## 11. Begriffsdefinition: Turn

- Ein `Turn` ist eine abgeschlossene Interaktionseinheit innerhalb einer Session.
- Ein Turn enthaelt mindestens:
  - Wearer-Eingabe (`player_action`/Chatnachricht)
  - KI-Antwort (`ai_narration`/Chatantwort)
  - optional ausgefuehrte Aktionen inklusive Resultat
  - Zeitstempel und Turn-Nummer
- Turn-Daten sind die persistierten Daten dieser Interaktionseinheit fuer Audit, Export und Recovery.

## 12. Entscheidungsstand (Rueckfragen geklaert)

1. Verschluesselung Bilder:
- bestaetigt: AES-256-at-rest mit zentralem Key-Management fuer MVP.
- bestaetigt: PGP wird vorerst nicht umgesetzt und nur bei spaeterem begruendetem Bedarf geprueft.

2. Hard-Stop Semantik:
- bestaetigt: Hard-Stop stoppt KI-Aktionen und setzt externe Integrationen in einen sicheren Zustand.

3. 2-Phasenfreigabe TTLock:
- bestaetigt: Wearer bestaetigt Phase 2 selbst.
- bestaetigt: keine zusaetzliche Re-Authentifizierung erforderlich.

4. Bildbeurteilung:
- bestaetigt: nicht bestandene Kontrolle darf automatische Folgeaktionen ausloesen.

5. Exportformat:
- bestaetigt: JSON und signierter PDF-Bericht.
