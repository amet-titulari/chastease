# Changelog

## 0.3.1 - 2026-03-04

- Refactory/Stabilisierung:
  - Test-Suite wieder lauffähig gemacht (Syntax-Fix in `tests/conftest.py`, pytest-sichere Main-Guards für lokale Analyse-Skripte).
  - Live-Snapshot-Erzeugung für KI korrigiert (JSON-Parsing für `policy_snapshot_json` und `psychogram_snapshot_json`).
  - Live-Read-Token-Zugriff harmonisiert (`X-AI-Access-Token` Header plus Query-Param-Kompatibilität für `ai_access_token`).
  - Kompatibilitäts-Fallbacks für lokale/restriktive Umgebungen ergänzt (`slowapi`- und `argon2`-Fallbacks), ohne produktives Standardverhalten zu ändern.
- Verifikation:
  - Vollständiger Testlauf erfolgreich: `129 passed`.

## 0.3.0 - 2026-03-03

- Setup-/Psychogramm-Flow weiter ausgebaut:
  - Basis-Konfiguration erweitert (Anweisungsstil, Intensität, Intimrasur-Präferenz) und AI-Kalibrierung im UI vor den Speichern-Block verschoben.
  - LLM/Integrationen als Voraussetzung für psychogrammgestützte Fragenfluss-Elemente konsolidiert.
  - Defaults für Vertrags-/Session-Parameter und Psychogramm-Werte überarbeitet.
- KI-gesteuerte Session-Anpassungen erweitert:
  - Zusätzliche Policy-/Psychogramm-Felder als AI-kontrollierbar markiert (inkl. Audit-Log-Transparenz).
  - Hygiene-/Öffnungslogik im Chat-Fallback gehärtet (inkl. State-Checks und Siegel-Mode-abhängiger Eingaben).
- Chat-UX verbessert:
  - Hintergrund, Composer und Scroll-Verhalten verfeinert, sodass letzte Nachricht und Eingabefeld zuverlässig sichtbar bleiben.
  - Bild-Upload/Paste-Flow ergänzt und „schwebende Punkte“ durch neutrales Lade-Feedback ersetzt.
- Psychogramm-Mapping korrigiert:
  - Eskalationsmodus priorisiert nun die explizite Psychogramm-Antwort vor Defaults.
  - Erfahrungsprofil-Schwellen angepasst (`40/100` wird als `intermediate` eingeordnet).

## 0.2.0 - 2026-02-26

- Notfall-/Abbruchlogik auf Session-Ebene neu ausgerichtet:
  - Notfallabbruch nutzt nun den direkten `ttlock_open`-Pfad.
  - Session/Vertrag werden erst nach erfolgreicher Notfalloeffnung invalidiert/archiviert.
  - Trigger-/Bestaetigungs-Erkennung fuer Notfallabbruch gehaertet.
- Oeffnungslimits serverseitig verbindlich gemacht:
  - `opening_limit_period` + `max_openings_in_period` werden bei Oeffnungen durchgesetzt.
  - Runtime-Tracking fuer Oeffnungsereignisse eingefuehrt.
- Chat/UI- und Betriebsverbesserungen:
  - Bildverifikation als schlanker One-Button-Flow mit Vorschau/Status.
  - Dashboard-/Session-Polling reduziert (Cache + Dedupe).
  - Robustere Filterung von Machine-Tags in Narrationen.

## 0.1.11 - 2026-02-26

- Notfall-/Abbruch-Flow korrigiert und gehaertet:
  - Notfallabbruch fuehrt nun direkt `ttlock_open` aus (statt `hygiene_open`) fuer die Tresor-Notfalloeffnung.
  - Session/Vertrag werden erst nach erfolgreicher Notfalloeffnung archiviert/invalidiert.
  - Trigger-Erkennung fuer Notfallabbruch erweitert (`rot/red`, `abbruch`, `notfall`, `stop/stopp`, etc.).
  - Bestaetigungs-Erkennung fuer Abbruch erweitert (`abbrechen`, `beenden`, `stop/stopp`, `rot/red`), damit der Confirm-Counter nicht haengen bleibt.
- Chat-Action- und Vision-Flow verbessert:
  - Bildverifikation auf schlanken One-Button-Flow umgestellt (`Bild aufnehmen` -> Vorschau -> `Bild prüfen`).
  - JSON-Payload in der Image-Action-Card ausgeblendet; Anforderung/Verifikation besser lesbar gemacht.
  - Vision-Review auf kurze Bewertung ohne separate Bildbeschreibung umgestellt.
- Robustheit/Traffic:
  - Dashboard-/Session-Polling gedrosselt und zentral per Cache/In-Flight-Dedupe optimiert.
  - Maschinen-Tags in Narration gehaertet, damit rohe `[[REQUEST...]]`-Fragmente nicht im UI erscheinen.
  - Server-seitige Oeffnungslimits fuer TTLock gehaertet (`opening_limit_period` + `max_openings_in_period`) inkl. Runtime-Tracking pro Periode.
  - Hotfix fuer `NameError` im TTLock-Open-Pfad nach Limit-Pruefung (Helper-Funktionen auf Modulscope verschoben).

## 0.1.10 - 2026-02-25

- Chat- und Aktionsfluss deutlich robuster gemacht:
  - Striktes Request-Tag-Verhalten fuer LLM-Aktionen inklusive Repair-Round/Diagnostik erweitert.
  - Timer- und Freeze/Pause-Handling stabilisiert (Alias-Mapping, Boundary-Clamping, verlässlichere Ausführung).
  - Hygiene-Flow im Chat verbessert: kompaktere Action-Karten, aktive Countdown-Karte mit direktem Beenden.
- Setup-/Session-Persistenz fuer Integrationen weiter vereinheitlicht:
  - DB-first Integrations-Updates fuer aktive Session + Setup-Sync gefestigt.
  - Setup uebernimmt nun auch TTLock-Konfiguration aus der letzten Session als Seed.
- Dashboard-/UI-Polish:
  - Pausenstatus-Visualisierung (inkl. Symbolik) und Runtime-Timer-Anzeige verfeinert.
- Tests erweitert:
  - Zusätzliche Regressionstests fuer Chat-Aktionen, Narration-Aliasing und Setup-TTLock-Seed.

## 0.1.9 - 2026-02-25

- Vertrags-/Consent-Flow weiter stabilisiert:
  - Contract-Seite bindet `session.js` korrekt ein (Fix fuer "Session helper nicht verfuegbar").
  - Nach Setup-Abschluss mit Vertragsgenerierung erfolgt direkte Weiterleitung auf `/contract` fuer sofortigen Digital-Consent.
  - Contract-Seite liest Vertragsdaten robust (aktive Session + Setup-Session-Fallback) und aktualisiert den signierten Zustand nach Consent sofort.
- Markdown-Rendering fuer Artefakte eingefuehrt:
  - Vertragstext auf `/contract` wird als Markdown dargestellt.
  - Psychogramm-Analyse im Dashboard wird als Markdown dargestellt.
  - Lokaler, sicherer Markdown-Renderer in `static/js/common.js` hinzugefuegt (ohne externe CDN-Abhaengigkeit).
- Tests erweitert:
  - Neuer Setup-Flow-Test validiert den Consent-Uebergang (`pending -> accepted`) inklusive Sichtbarkeit in `/sessions/active`.
  - Web-Test fuer `/contract`-Seite inklusive Script-Einbindung (`session.js`, `contract.js`).

## 0.1.8 - 2026-02-25

- Setup-Prozess erneuert:
  - Accordion-Flow und Schrittreihenfolge konsolidiert (Basis -> Psychogramm -> LLM -> TTLock/Chaster -> Abschluss -> Artefakte).
  - Integrationskarten (TTLock/Chaster) als eigene Schritte mit kontrollierter Sichtbarkeit nach Speichern in der Basis-Konfiguration.
  - LLM-UX verfeinert: Ghost-Button fuer Live-Test mit Laufzeit-Glow; Speichern wird erst nach erfolgreichem Test sichtbar/aktiv.
  - Warn-/Bestaetigungsstufe vor Setup-Abschluss hinzugefuegt.
- Dashboard-/Session-Statusanzeige stabilisiert:
  - `setup_status` wird auch bei aktiver Session konsistent mitgeliefert.
  - Frontend-Fallback auf irrefuehrendes `draft` entfernt.
- UI-Konsistenz verbessert:
  - Speichern-Buttons auf einheitliches Blau vereinheitlicht.
  - Sekundaere Aktionsbuttons stilistisch harmonisiert und Beschriftungen in Deutsch vereinheitlicht.

## 0.1.7 - 2026-02-25

- Frontend: Auth-Formulare getrennt und UX verbessert:
  - Login zeigt nur `Benutzername` und `Passwort`.
  - Registrierung zeigt `Benutzername`, `E-Mail`, `Passwort` und `Passwort-Bestätigung`.
  - Clientseitiges JS steuert den Auth-Mode über den URL-Parameter `mode` und validiert Passwort-Matching.
- Tests: Frontend-Änderungen verifiziert; Test-Suite grün.
- Kleinere Refactor- und Stabilitätsfixes im UI/Router-Bereich.

## 0.1.6 - 2026-02-25

- Setup-/Session-Stabilisierung:
  - Setup-Start mit `integrations=["ttlock"]` funktioniert auch ohne verpflichtende `integration_config`.
  - `POST /api/v1/setup/sessions/{id}/complete` aktiviert nun sofort eine persistente aktive Session.
  - Setup-/Session-/Story-Flow-Regressionen behoben (voller Testlauf wieder gruen).
- Frontend-Migration weitergezogen:
  - Jinja2-Templates + Static-Mount als Standardpfad fuer Web-Seiten gefestigt.
  - `/app`-Route auf schlanken Template-Renderer bereinigt (kein Legacy-Inline-HTML mehr im Router).
- Doku-/Release-Sync:
  - Projektstatus und Teststand auf aktuellen Stand aktualisiert.
  - Versionen harmonisiert (`VERSION`, App-Metadaten, Changelog).

## 0.1.4 - 2026-02-24

- LLM-Defaults fuer Setup/Profil aktualisiert:
  - Chat-Default auf `grok-4-1-fast-non-reasoning`.
  - Vision-Default auf `grok-4-latest`.
- Setup-Defaults fuer TT-Lock angepasst:
  - Integration standardmaessig auf `yes`.
  - Benutzername standardmaessig mit `eritque.clausus@gmx.net` vorbelegt.
- Provider-Robustheit verbessert:
  - LLM Timeout/Retry-Defaults erweitert und in `.env.example` dokumentiert.
- Chat UX verbessert:
  - Bildverifikation zeigt KI-Narration direkt nach erfolgreicher Pruefung.
  - Sekundaerer Refresh-Fehler ueberschreibt den Erfolg nicht mehr.
  - Neuer Floating-Button fuer schnellen Sprung nach oben im langen Chat.
- Action-Parsing gehaertet:
  - `[[REQUEST:...]]`/`[[ACTION:...]]`/`[[FILE|...]]` werden jetzt auch mit mehrzeiligem JSON robust erkannt.
  - Regressionstest fuer mehrzeiligen `image_verification`-Request hinzugefuegt.

## 0.1.3 - 2026-02-24

- Hygiene-Flow und TT-Lock-Aktionen klar getrennt:
  - `hygiene_open`/`hygiene_close` fuer Hygieneoeffnung in Chat-Aktionen eingefuehrt.
  - `ttlock_open`/`ttlock_close` im Chat-Flow reserviert und gegen direkte Ausfuehrung abgesichert.
- Setup-Validierung fuer TT-Lock verschaerft:
  - Start wird mit klarer Fehlermeldung abgelehnt, wenn `ttl_user`, `ttl_pass_md5` oder `ttl_lock_id` fehlen.
- Chat-UX fuer Hygieneoeffnung ueberarbeitet:
  - Bestaetigung, Ausfuehrungsstatus, Countdown, manuelles Beenden und Timeout-Strafe konsistent abgebildet.
  - AI-Follow-up erfolgt erst nach `hygiene_close` oder Timeout.
- x.ai Response-Parsing robuster gemacht und durch Regressionstests abgesichert.

## 0.1.2 - 2026-02-24

- Setup-Prozess funktioniert korrekt und stabil im End-to-End-Flow (Analyse, Vertragsentwurf, Rueckgabe).
- Vertragsgenerierung auf strukturierte Abschnitts-Edits umgestellt:
  - LLM liefert JSON-Edits statt kompletten Vertragstext.
  - Signatur- und Footer-Bereich bleiben strukturell geschuetzt.
  - Gueltige Edits werden gezielt auf Template-Abschnitte angewendet.
- Erweiterte DEBUG-Logs fuer Contract-Edits:
  - Eingehende Edit-Payload, akzeptierte Edits und angewendete Abschnittsaenderungen werden nachvollziehbar geloggt.

## 0.1.1 - 2026-02-23

- TT-Lock-Integration von Setup bis Ausfuehrung erweitert:
  - Setup-Card fuer TT-Lock mit Discover-Flow (Gateways/Locks) und Persistenz von `integration_config`.
  - Neuer API-Endpoint fuer Device-Discovery: `POST /api/v1/setup/ttlock/discover`.
  - Reale Action-Ausfuehrung fuer `ttlock_open`/`ttlock_close` in `chat/actions/execute`.
- Bildverifikations-UX in der Chat-Action-Card verbessert:
  - Upload-Option entfernt, nur noch Fotoaufnahme.
  - Nach Bilduebermittlung werden Buttons ausgeblendet und Status "Pruefung laeuft" angezeigt.
- Dashboard/Setup-Flow korrigiert:
  - Ohne aktive Session wird nur der Setup-Bereich angezeigt.
  - Nach Session-Kill kein Dashboard-Hin-und-her mehr.
- Provider-Stabilitaet/Observability gehaertet:
  - Erweitertes Fehler-Logging fuer Upstream-Timeouts/HTTP-Fehler inkl. Diagnosekontext.
  - Retry/Backoff-Strategie fuer LLM-Calls verbessert (inkl. `Retry-After`-Beruecksichtigung).
  - TT-Lock API-Calls mit robusteren Retries und laengeren Action-Timeouts.
- Regressionstests erweitert fuer Setup-, Discover-, Chat- und TT-Lock-Pfade.

## 0.1.0 - 2026-02-23

- R1 Refactoring-Milestone erreicht.
- API-Refactoring umgesetzt:
  - Request-Schemas ausgelagert nach `src/chastease/api/schemas.py`.
  - Questionnaire/Translations ausgelagert nach `src/chastease/api/questionnaire.py`.
  - Feature-Router physisch getrennt unter `src/chastease/api/routers/` (`auth`, `llm`, `users`, `story`, `chat`, `sessions`, `setup`, `system`).
- Setup-Entkopplung umgesetzt:
  - Setup-Domain-Regeln in `src/chastease/api/setup_domain.py`.
  - Infrastruktur-/AI-Ports fuer Setup in `src/chastease/api/setup_infra.py` und `src/chastease/api/setup_ai.py`.
  - Setup-Endpunkte in `src/chastease/api/routers/setup.py` konsolidiert.
- Web-Refactoring umgesetzt:
  - Web-Router aufgeteilt in `src/chastease/web/routers/public.py`, `src/chastease/web/routers/app.py`, `src/chastease/web/routers/chat.py`.
  - `src/chastease/web/routes.py` auf Router-Aggregation reduziert.
- Test-Gate erreicht:
  - Testlauf in Python-3.12-venv (`.venv312`) erfolgreich: `27 passed`.
- Vertrags-/Consent-Flow stabilisiert:
  - Vertragstext bleibt stabil, Consent wird als technische Information im JSON gepflegt.
  - Contract-Seite: Consent erst bei vorhandenem Vertrag sichtbar, nach Akzeptanz nur kompakte Bestaetigungsnotiz.
  - Dashboard/Contract-Navigation repariert (Setup-Session-Fallback ueber aktive Session).

## 0.0.10 - 2026-02-21

- Neue dedizierte Seite `/chat` mit modernem Chat-Layout eingefuehrt (inspiriert von ChatGPT/Perplexity/Gemini-Flow).
- Chat-Features auf `/chat`:
  - Text-Chat
  - Bild-/Datei-Upload (inkl. Screenshots/Anhänge)
  - Voice-Diktat im Browser (Web Speech API, falls verfuegbar)
  - Export letzter Antwort als TXT/JSON
  - Download von durch KI gelieferten Dateiantworten (`generated_files`)
- API Chat-Responses erweitert:
  - `generated_files` wird in `/api/v1/chat/turn` und `/api/v1/setup/sessions/{id}/chat-preview` mitgeliefert.
  - Marker-Parsing fuer Dateiantworten unterstuetzt (`[[FILE|{...}]]`).
- Psychogramm-Form korrigiert:
  - Skalen wieder als Slider statt Textfelder (kompatibel fuer `scale_100`, `scale_10`, `scale_5`).
  - Ampelsystem ohne Eingabefelder umgesetzt (nur feste Anzeige mit Gruen/Gelb/Rot-Definition).
- Landingpage und App-Topbar um direkten Link auf `/chat` erweitert.

## 0.0.9 - 2026-02-21

- Complete-Setup-Bestaetigung verhaelt sich nun final: `Start Setup`, `Psychogram`, `AI Configuration` und `Complete Setup` werden sofort gesperrt.
- `AI Chat`, `Psychogram Brief` und `Response` bleiben nach der Bestaetigung fuer Analyse/Debug offen.
- Nach Bestaetigung wird direkt in den `Psychogram Brief` gewechselt und waehrend Verarbeitung `Analyse in arbeit` angezeigt.
- Session-Kill-Flow bleibt testbar: nach Loeschen wird wieder ein `draft`-Setup bereitgestellt.
- Dokumentation auf Implementierungsstand 0.0.9 synchronisiert (Flow, Auth-Stand, Psychogramm-Schema, Backlog-Erweiterungen).

## 0.0.8 - 2026-02-21

- App-Flow auf Accordion umgestellt: Start Setup, Psychogram, AI Configuration, Complete Setup, AI Chat, Psychogram Brief, Response.
- Nur eine Karte gleichzeitig offen; Folgekarten bis erfolgreichem Setup-Start gesperrt.
- Auto-Navigation im Setup-Flow: Start -> Psychogram, Submit Answers -> AI Configuration, Save LLM Profile -> Complete Setup.
- Dashboard/Chat entkoppelt, Home/Dashboard/Logout oben rechts konsolidiert.
- Setup-Form verbessert: Penalty-Felder werden bei deaktivierten Caps ausgeblendet.
- Datumslogik bidirektional synchronisiert (Start, Max End, Max Duration), inklusive `0 Tage = KI entscheidet Enddatum`.
- UI-Texte für DE/EN zentralisiert und breit übersetzt.
- Psychogramm v2.4 erweitert:
  - `interaction_preferences`: `escalation_mode`, `experience_level`, `experience_profile`
  - `safety_profile`: `mode`, optional `safeword`, optional `traffic_light_words`
  - `personal_preferences`: `grooming_preference`
- Safety-Validierung ergänzt: abhängige Pflichtfelder werden über `q10_safety_mode` erzwungen.
- Questionnaire um Sicherheits-/Eskalations-/Grooming-/Erfahrungsfelder erweitert.
- Psychogramm-UI zeigt je nach `safety_mode` nur relevante Sicherheitsfelder.

## 0.0.6 - 2026-02-21

- Auth-Flow auf Username/Password fokussiert, Registrierung mit Pflichtfeld E-Mail.
- Aktive Session erzwingt Dashboard statt neuem Setup; Setup-Guard gegen parallele aktive Sessions.
- Session-Vertrag im Setup erweitert (Startdatum, KI-gesteuertes Enddatum mit optionalem Max-Enddatum, Limits/Opening-Period).
- Psychogramm-/Setup-UI verbessert: kompakteres responsives Layout, bessere Mobil-Darstellung, i18n fuer Dropdown-Werte.
- Session-Kill als Feature-Flag eingefuehrt (`ENABLE_SESSION_KILL`), inklusive API-Endpoint und Dashboard-Button.
- Frontend-Flow verfeinert: Login-Karte ausblendbar nach Login, Logout oben rechts, Session-KILL fuer erneuten Setup-Durchlauf.

## 0.0.5 - 2026-02-21

- User-First Setup eingefuehrt (`/users`, `/users/{id}`, `/users/{id}/characters`).
- Setup-Start auf `user_id` umgestellt, optional mit `character_id`.
- Persistente Sessiondaten auf `user_id`/`character_id` angepasst.
- Landingpage (`/`) und App-Shell (`/app`) eingefuehrt.
- Alte Demo-Route als Redirect auf `/app` weitergefuehrt.
- Tests fuer User-Setup und Web-Seiten erweitert.

## 0.0.4 - 2026-02-21

- Psychogramm-Feedback umgesetzt: dynamische Updates, `update_reason`, `autonomy_profile`, `autonomy_bias`, `praise_timing`.
- Sicherheits- und Filterfelder erweitert (`blocked_trigger_words`, `forbidden_topics`, Challenge-Kategorien).
- Konservative Defaults bei niedriger Psychogramm-Confidence explizit implementiert.
- Fragebogen auf Session-Setup v2.1 (8 Hauptfragen + offene Abschlussfrage) umgestellt.
- Kurzauswertung `psychogram_brief` in API-Responses und Demo-UI integriert.

## 0.0.3 - 2026-02-21

- Setup-Prototyp funktional ausgebaut (Start, Fragebogen, Preview, Abschluss).
- BDSM-test-inspirierter Fragebogen mit Psychogramm-Ableitung integriert.
- Mehrsprachigkeit im Prototyp erweitert (`de`/`en`) fuer Setup und Story-Turn.
- Fragebogenskala auf `1-10` umgestellt, inklusive Slider-UI in der Demo.
- Datei-basierte Persistenz fuer Setup-Sessions (`data/setup_sessions.json`) eingefuehrt.
- Tests fuer Setup-Flow, i18n und Demo erweitert.

## 0.0.2 - 2026-02-21

- Produkt-, Architektur- und SRS-Dokumente konsolidiert und sprachlich/fachlich geschärft.
- Domains `world` und `combat` vollständig aus allen Dokumenten entfernt.
- `GameSession` konsistent auf `ChastitySession` umgestellt.
- Setup/Initialisierung in Priorität P0 aufgenommen.
- Psychologischer Setup-Fragebogen und Psychogramm-Konzept ergänzt.
- Neues Architekturartefakt: `docs/architecture/PSYCHOGRAM_SCHEMA.md`.

## 0.0.1 - 2026-02-21

- Initiale Projektgrundlage mit API, Tests und Dokumentationsstruktur.
- Architektur- und Anforderungsdokumentation mit C4, UML, Action-Matrix und ADRs.
- Migration des API-Scaffolds von Flask auf FastAPI.
- UI/UX-Anforderungsschicht fuer responsive, geraeteuebergreifende Nutzung.
