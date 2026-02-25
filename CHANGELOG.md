# Changelog

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
