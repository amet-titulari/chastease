# Benutzeranleitung – Chastease

Diese Anleitung erklärt Schritt für Schritt, wie du Chastease einrichtest und nutzt.

---

## Inhaltsverzeichnis

- [Benutzeranleitung – Chastease](#benutzeranleitung--chastease)
  - [Inhaltsverzeichnis](#inhaltsverzeichnis)
  - [1. Registrierung \& Login](#1-registrierung--login)
  - [2. Ersteinrichtung (Onboarding)](#2-ersteinrichtung-onboarding)
    - [Schritt 1 – Persona wählen](#schritt-1--persona-wählen)
    - [Schritt 2 – Dein Profil](#schritt-2--dein-profil)
  - [3. Dashboard](#3-dashboard)
  - [4. Neue Session starten](#4-neue-session-starten)
  - [5. Play-Ansicht – Übersicht](#5-play-ansicht--übersicht)
  - [6. Chat mit der Keyholderin](#6-chat-mit-der-keyholderin)
  - [7. Aufgaben \& Aktionskarten](#7-aufgaben--aktionskarten)
    - [Aufgaben erhalten](#aufgaben-erhalten)
    - [Aktionskarten](#aktionskarten)
    - [Konsequenzen](#konsequenzen)
  - [8. Bildverifikation](#8-bildverifikation)
    - [Ablauf](#ablauf)
  - [9. Sicherheitssystem (Ampel, Safeword, Notfall)](#9-sicherheitssystem-ampel-safeword-notfall)
    - [Ampelsystem](#ampelsystem)
    - [Safeword](#safeword)
    - [Notfallentlassung](#notfallentlassung)
  - [10. Hygiene-Öffnung](#10-hygiene-öffnung)
  - [11. Dashboard und Schnellaktionen](#11-dashboard-und-schnellaktionen)
  - [12. Session History \& Export](#12-session-history--export)
  - [13. Verträge](#13-verträge)
  - [14. Scenarios und Phasen bearbeiten](#14-scenarios-und-phasen-bearbeiten)
  - [15. Multi-Device-Nutzung](#15-multi-device-nutzung)
  - [16. Posture-Import/Export (ZIP)](#16-posture-importexport-zip)
  - [Datenschutz \& Sicherheit](#datenschutz--sicherheit)

---

## 1. Registrierung & Login

Öffne die App im Browser (Standard: `http://<server-ip>:8000`).

- **Registrieren**: Klicke auf „Registrieren", gib einen Benutzernamen (mind. 3 Zeichen) und ein Passwort (mind. 8 Zeichen) ein. Danach wirst du automatisch eingeloggt und zur Ersteinrichtung weitergeleitet.
- **Einloggen**: Gib Benutzername und Passwort ein. Dein Session-Token bleibt 30 Tage gültig, solange du den Browser nicht schließt oder abmeldest. Du kannst dich auf mehreren Geräten gleichzeitig einloggen, ohne gegenseitig abgemeldet zu werden.
- **Abmelden**: Ueber die Kopfnavigation oben rechts → „Logout".

---

## 2. Ersteinrichtung (Onboarding)

Beim ersten Start (oder wenn kein Profil vorhanden ist) wirst du durch ein kurzes Onboarding geführt.

### Schritt 1 – Persona wählen
Wähle die Persönlichkeit deiner Keyholderin aus den verfügbaren Voreinstellungen oder passe sie individuell an.

### Schritt 2 – Dein Profil
Gib deine Präferenzen an:

| Feld | Bedeutung |
|---|---|
| **Grenzen / Limits** | Was ist absolut ausgeschlossen? Diese Informationen werden direkt an die KI weitergegeben. |
| **Stil / Intensität** | Wie streng oder fürsorglich soll die Keyholderin sein? |
| **Dein Ziel** | Warum nutzt du Chastease? (z.B. Ausdauer trainieren, Kontrolle abgeben) |
| **Szenario-Preset** | Standardszenario für neue Sessions |

Klicke „Weiter" – die Einstellungen werden gespeichert und stehen der KI sofort zur Verfügung.

---

## 3. Dashboard

Das Dashboard (`/dashboard` bzw. `/dashboard/{session_id}`) ist die zentrale Spieleroberflaeche nach dem Login.

- **Aktive Session**: Status, verbleibende Zeit, Session-Rahmen und direkte Navigation zur Play-Ansicht.
- **Beziehungswerte**: Trust, Obedience, Resistance, Favor, Strictness, Frustration und Attachment bleiben als langfristige Session-Gesamtbeurteilung sichtbar.
- **Seit Start**: Der blaue Bereich zeigt den Startwert, der gruene Bereich die Entwicklung seit Session-Beginn.
- **Phasenfortschritt**: Rechts daneben gibt es eine eigene Karte fuer die aktive Phase. Dort starten alle Phasenpunkte je Kriterium wieder bei `0` und laufen bis zu den Zielwerten dieser Phase.
- **Phasenwechsel**: Beim Wechsel in die naechste Phase werden die Phasenpunkte zurueckgesetzt; die langfristigen Beziehungswerte bleiben erhalten.
- **Wichtig**: Fuer diese Punkte zaehlen nur Aufgaben, die in der aktuellen Phase entstanden sind; alte oder doppelte Tasks sollen die neue Phase nicht kuenstlich beschleunigen.
- **Safety/Hygiene**: Ampelaktionen, Safeword, Hygiene-Kontingente und Oeffnungen sind direkt im Dashboard gebuendelt.
- **Navigation**: Auf allen authentifizierten Seiten ist dasselbe Hauptmenue sichtbar; Landing und Login bleiben absichtlich reduziert.

---

## 4. Neue Session starten

1. Klicke auf „Neue Session starten" im Dashboard oder navigiere zu `/experience` (`Chat` in der Hauptnavigation).
   Für einen schnelleren Solo-Einstieg kannst du dort auch **Quick Start** wählen und direkt zur Session-Erstellung springen.
2. Wähle oder bestätige die Persona-Auswahl.
3. Wähle oder bearbeite das Scenario direkt im Onboarding.
   Im Scenario koennen Phasen mit Titel, Ziel, Guidance sowie optionalen Zielwerten (`score_targets`), Gewichtung und Mindestdauer gepflegt werden.
4. Wähle die Sperrdauer:
   Trägst du nur eine Mindest-Freigabe ein, arbeitet die Session effektiv mit dieser festen Dauer.
   Wenn zusätzlich eine Max-Freigabe gesetzt ist, wird die tatsächliche Laufzeit beim Vertragsstart zufällig innerhalb dieser Spanne festgelegt.
5. In „Regeln" gelten **Standard-Penalty (Wert)** und **Max-Penalty (Wert)** immer in der gewählten **Einheit** (Minuten/Stunden/Tage).
6. Hinterlege im Vertragsrahmen die inhaltlichen Eckpunkte der Vereinbarung:
   Ziel, Methode/Geraet, Trageweise, Berührungsregeln, Orgasmusregeln, Belohnungen sowie Widerruf.
7. Schließe den digitalen Vertrag ab – er dokumentiert die Vereinbarungen für diese Session.
8. Nach dem Signieren startet die Session und du gelangst zur Chat-Ansicht.

Hinweis zu Vertragsaenderungen:
Vertrags-Addenda koennen spaeter den Vertragsrahmen (`Mindest-Freigabe`, `Max-Freigabe`), Session-Policies (z. B. Hygiene-Limits oder Penalty-Parameter) und aktive Protokollregeln aendern.
Die aktuell verbleibende Restzeit ist bewusst kein Vertragsbestandteil; sie bleibt task- und ereignisgesteuert.
Wenn `Mindest-Freigabe` oder `Max-Freigabe` waehrend einer aktiven Session geaendert werden, wird nur geprueft, ob die bereits gezogene Gesamtdauer noch innerhalb des neuen Rahmens liegt.

---

## 5. Play-Ansicht – Übersicht

Die Play-Ansicht (`/play`) ist die Hauptoberfläche waehrend einer aktiven Session.
Sie ist jetzt bewusst als Chat-Flaeche reduziert; Sessiondaten, Einstimmung, Safety/Hygiene und Spielresultate liegen im separaten Dashboard (`/dashboard/{session_id}`).

```
┌─────────────────────────────────┐
│  [Persona] [Tasks ①] [⚙ ]      │  ← Header
├─────────────────────────────────┤
│                                 │
│  Chat-Timeline                  │
│  (Nachrichten + Aktionskarten)  │
│                                 │
├─────────────────────────────────┤
│  [Nachricht eingeben…] [↑]      │  ← Eingabe
└─────────────────────────────────┘
```

- **Header links**: Persona-Name, Session und Status.
- **Tasks-Badge**: Zeigt die Anzahl offener Aufgaben. Rotes Badge = dringende Aufgaben vorhanden.
- **Dashboard**: Fuehrt zur zentralen Session-Uebersicht mit Rahmen, Einstimmung und Spieler-Infos.
- **Chat-Timeline**: Alle Nachrichten chronologisch; Aktionskarten erscheinen am Ende.
- **Persona-Avatar**: Neben jeder KI-Nachricht wird das Avatar-Bild der aktuellen Persona angezeigt (sofern vorhanden).
- **Betriebshinweise**: Wenn der LLM-Provider gestoert ist, erscheint ein sichtiger Hinweis im Play-Screen; die Session laeuft dann voruebergehend in reduziertem Modus.
- **Navigation**: Die obere App-Navigation bleibt auf Play, Dashboard, Vertrag, Profil und weiteren authentifizierten Seiten konsistent.

---

## 6. Chat mit der Keyholderin

Tippe deine Nachricht ins Eingabefeld und drücke Enter oder den Sende-Button.

Die KI antwortet im Charakter der gewählten Persona. Sie kennt:
- Deine Grenzen und Limits
- Deinen bevorzugten Stil
- Das aktuelle Session-Szenario
- Alle offenen Aufgaben (damit sie darauf referenzieren und bei Nicht-Erfüllung reagieren kann)

**Hinweise:**
- Der Chat läuft über WebSocket – Nachrichten erscheinen als Stream in Echtzeit.
- Die KI kann eigenständig Aufgaben erstellen, Zeit hinzufügen oder Tasks als fehlgeschlagen markieren.
- Während des Chats aktive Sicherheitsampel-Zustand (z.B. Gelb) beeinflusst den Ton der Antworten.

---

## 7. Aufgaben & Aktionskarten

### Aufgaben erhalten
Aufgaben können auf verschiedene Wege entstehen:
- Die **KI erstellt sie selbst** im Gespräch (via `create_task`-Action).
- Du wirst durch die Keyholderin direkt im Chat darauf hingewiesen.

### Aktionskarten
Für jede offene Aufgabe erscheint am Ende der Chat-Timeline eine **Aktionskarte**:

```
┌──────────────────────────────────────┐
│ 📋 #3          ⏰ noch 12 Min        │
│ Aufgaben-Titel                       │
│ Beschreibung der Aufgabe…            │
│                                      │
│ [✓ Bestätigung] [✗ Fail]             │
│ oder: [📷 Fotoverifikation] [✗ Fail] │
└──────────────────────────────────────┘
```

- **Task-Nummer** (`#3`): Jede Karte zeigt die eindeutige Task-ID.
- **Deadline** (rechts): Verbleibende Zeit bis zur Frist. Farbcodiert: normal (weiß), bald fällig (gelb, < 10 Min), überfällig (rot).

| Button | Aktion |
|---|---|
| **Bestätigung** | Markiert den Task als abgeschlossen; Belohnung (z.B. Zeitabzug) wird angewendet. |
| **Fail** | Markiert den Task als nicht erfüllt; Strafe (z.B. Zeitverlängerung) wird angewendet. |
| **Fotoverifikation** | Öffnet die Foto-Verifikation (nur wenn der Task Verifikation erfordert). |

Das **Tasks-Dropdown** im Header (über das Badge erreichbar) zeigt alle offenen Aufgaben als **interaktive Aktionskarten** – du kannst Tasks direkt aus dem Dropdown heraus bestätigen, als fehlgeschlagen markieren oder zur Fotoverifikation öffnen.

### Konsequenzen
Konsequenzen werden automatisch als Session-Event protokolliert und im Chat als Systemmeldung angezeigt. Beispiele:
- „⏳ +30 Minuten wurden hinzugefügt (Task-Strafe)"
- „✅ −15 Minuten wurden abgezogen (Task-Belohnung)"

---

## 8. Bildverifikation

Die Bildverifikation wird genutzt, wenn die Keyholderin eine nummerierte Plombe als Beweis anfordert.

### Ablauf
1. Klicke auf **„Verifizieren"** in der Aktionskarte des entsprechenden Tasks.
2. Ein Foto-Upload-Feld erscheint direkt in der Karte.
3. Mache ein Foto mit der aktuellen Plombre-Nummer (die erwartete Nummer wird angezeigt).
4. Lade das Bild hoch – die KI analysiert es automatisch.
5. Das Ergebnis (Bestätigt / Abgelehnt) erscheint in der Karte und als Chat-Systemmeldung.

**Hinweis:** Bilder werden nur auf dem Server gespeichert, nicht im Browser-Cache oder der Galerie. Chat-Verifikationen erhalten Dateinamen nach dem Schema `session<id>-chat-task<task_id>-<timestamp>.<ext>`.

---

## 9. Sicherheitssystem (Ampel, Safeword, Notfall)

Das Sicherheitssystem ist jederzeit verfuegbar und ueberschreibt immer den normalen Session-Ablauf.

### Ampelsystem
Druecke im Dashboard oder in der Play-Ansicht ueber die schnellen Ampel-Buttons:

| Farbe | Bedeutung | KI-Reaktion |
|---|---|---|
| 🟢 **Grün** | Alles in Ordnung | Normal |
| 🟡 **Gelb** | Unwohl / leichte Bedenken | Wechselt in fürsorglich-sorgenden Ton |
| 🔴 **Rot** | Stopp – sofortiger Rückzug | Session pausiert; KI deeskaliert aktiv |

### Safeword
Ueber den Safeword-Button. Die Session wird sofort in den roten Modus versetzt und protokolliert.

### Notfallentlassung
Ueber die Notfallaktion im geschuetzten Bereich. Beendet die Session sofort und erstellt einen vollstaendigen Safety-Log-Eintrag. Dieser Schritt ist **irreversibel**.

---

## 10. Hygiene-Öffnung

Eine Hygiene-Öffnung erlaubt eine zeitlich begrenzte Entsperrung für Reinigungszwecke.

1. Im Dashboard → „Oeffnung beantragen".
2. Die Dauer wird aus deinem Kontingent abgezogen (konfigurierbar im Vertrag).
3. Während der Öffnung läuft ein Countdown.
4. Klicke „Wieder verschließen" wenn du fertig bist – oder warte bis der Timer abläuft.

---

## 11. Dashboard und Schnellaktionen

Die fruehere Drawer-Logik ist reduziert. Relevante Session-Steuerung liegt jetzt an festen Stellen:

- **Dashboard**: Session-Info, Hygiene, Safety, Beziehungswerte und Spielresultate.
- **Play-Header**: Direkte Schnellaktionen fuer Tasks und Safety.
- **Kopfmenue**: Einheitliche App-Navigation zwischen Chat, Dashboard, Games, Profil und Admin-Bereichen.

---

## 12. Session History & Export

Unter `/history` findest du alle abgeschlossenen Sessions.

- **Details**: Klicke auf eine Session für Nachrichten, Events und Tasks.
- **PDF-Export**: Vollständiger Session-Report als PDF.
- **Event-Export**: JSON-Export aller protokollierten Events.

---

## 13. Verträge

Unter `/contracts` findest du alle unterzeichneten Verträge.

- Jede Session erzeugt einen Vertrag mit Bedingungen und Vereinbarungen.
- **Addenda**: Während aktiver Sessions können Zusatzvereinbarungen hinzugefügt werden.
- **PDF-Export**: Vertrag als PDF herunterladen.

---

## 14. Scenarios und Phasen bearbeiten

Unter `/scenarios` kannst du Scenarios anlegen, importieren, bearbeiten und exportieren.

- **Phasen**: Jede Phase besitzt Titel, Ziel und Guidance fuer die KI.
- **Phasen-Zielwerte**: Optional koennen pro Phase explizite Werte fuer `Trust`, `Obedience`, `Resistance`, `Favor`, `Strictness`, `Frustration` und `Attachment` gesetzt werden.
- **Gewichtung**: `phase_weight` bestimmt, wie stark eine Phase im Fallback gegenueber anderen Phasen gewichtet wird.
- **Mindestdauer**: `min_phase_duration_hours` dokumentiert, wie lange eine Phase mindestens tragen soll, bevor ein Wechsel dramaturgisch sinnvoll ist.
- **Fallback**: Wenn keine expliziten Zielwerte gesetzt sind, berechnet das Backend konservative Ziele aus Phase, Gewichtung und erwarteter Sessiondauer.

Praxis:

1. `/scenarios` oeffnen.
2. Scenario neu anlegen oder bestehendes Scenario bearbeiten.
3. In der Phasenliste pro Phase die Zielwerte pflegen.
4. Speichern und das Scenario anschliessend im Onboarding oder in einer neuen Session verwenden.

---

## 15. Multi-Device-Nutzung

Du kannst dich auf mehreren Geräten (z.B. Handy + Tablet) gleichzeitig einloggen. Beide Geräte nutzen dasselbe Session-Token und bleiben verbunden – ein neues Login meldet dich **nicht** auf anderen Geräten aus.

**Empfehlung:** Nutze denselben Browser-Tab nicht auf zwei Geräten gleichzeitig, da der WebSocket-Stream pro Tab verwaltet wird.

Wenn du eine abgeschlossene Session als Vorlage lädst, werden Konfiguration und LLM-Profil übernommen, aber Beziehung, Szene und Protokoll starten neu für die neue Session.
Proaktive Erinnerungen orientieren sich dabei an der aktuellen Szene, den aktiven Protokollregeln und dem frischen Phasenstand der neuen Session.

---

## 16. Posture-Import/Export (ZIP)

Du kannst alle Postures des Moduls gemeinsam als ZIP sichern und wieder einspielen.

Pfad: `/games` → Bereich **Postures verwalten**

- **Export**: Klicke auf „Alle Postures als ZIP exportieren".
- **Import**: Wähle eine ZIP-Datei und klicke „ZIP importieren (ersetzt alle)".

Wichtig:
- Der Import ersetzt immer den kompletten Posture-Bestand des Moduls.
- Bilder werden mit exportiert, sofern sie als lokale Upload-Bilder im System gespeichert sind.
- Beim Import werden Bilder erneut validiert (Format, Größe, Mindestauflösung) und normalisiert.
- Die ZIP enthält eine `manifest.json` und optional einen `images/`-Ordner.
- Ein einzelner Import kann nicht teilweise zurückgenommen werden.

---

## Datenschutz & Sicherheit

- Alle Daten bleiben auf deinem lokalen Server – keine Cloud, kein Tracking.
- Verifikationsbilder werden ausschließlich im `data/media/`-Verzeichnis auf dem Server gespeichert.
- Der Server sollte **nicht direkt ins Internet** exponiert werden. Nutze VPN (z.B. WireGuard, Tailscale) für externen Zugriff.
- Das Admin-Secret (`CHASTEASE_ADMIN_SECRET`) in der `.env`-Datei schuetzt sensible Admin-Steuer-Endpunkte wie `emergency-release` oder WS-Token-Rotation; normale Owner-Aktionen wie Ampelstatus oder Verifikations-Upload bleiben ohne zusaetzlichen Secret-Header nutzbar.
