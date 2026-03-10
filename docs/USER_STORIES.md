# User Stories – Chastease

## Persona: "Das Keuschling" (primärer Nutzer)

---

## Epics & Stories

### EPIC-01: Session starten

**US-01.1** – Session konfigurieren und starten
> Als Keuschling möchte ich vor dem Start einer Session die Mindest- und optionale Maximaldauer konfigurieren, damit der Zufall innerhalb meiner Grenzen arbeitet.

**Akzeptanzkriterien:**
- Eingabefeld für Mindestdauer (in Stunden/Tagen)
- Optionales Eingabefeld für Maximaldauer
- Auswahl der Keyholderin-Persona
- Bestätigung zeigt die zufällig berechnete Sperrdauer (ohne genaues Ende sichtbar zu machen, optional per Einstellung)
- Session ist nach Bestätigung aktiv und timer läuft

---

**US-01.2** – Keuschheits-Vertrag unterzeichnen
> Als Keuschling möchte ich vor dem Start der Session einen von der Keyholderin formulierten Vertrag lesen und digital unterzeichnen, damit die Session einen bindenden, feierlichen Charakter bekommt.

**Akzeptanzkriterien:**
- Nach der Konfiguration wird automatisch ein Vertrag generiert
- Der Vertrag ist im Ton und Stil der gewählten Keyholderin-Persona formuliert
- Alle wesentlichen Session-Parameter sind im Vertrag aufgeführt (Dauer, Regeln, Hygiene, Plomben, Safeword)
- Unterzeichnung erfordert eine aktive Bestätigung (keine versehentliche Aktivierung möglich)
- Erst nach Unterzeichnung startet der Timer; der Knopf ist vorher ausgegraut
- Ein Hinweis macht klar: nach Unterzeichnung sind keine eigenen Anpassungen mehr möglich

---

**US-01.3** – Keyholderin kennenlernen
> Als Keuschling möchte ich zu Beginn der Session von der Keyholderin begrüsst werden, damit ich sofort in die Rolle finde.

**Akzeptanzkriterien:**
- Automatische Begrüssung der Keyholderin beim Session-Start
- Ton und Stil entsprechen der konfigurierten Persona
- Optional: Kurzeinführung in die Regeln der Session durch die Keyholderin

---

### EPIC-02: Session-Alltag

**US-02.1** – Mit der Keyholderin chatten
> Als Keuschling möchte ich jederzeit mit der Keyholderin schreiben können, damit die Session lebendig bleibt.

**Akzeptanzkriterien:**
- Chat-Interface mit Nachrichtenverlauf
- Keyholderin antwortet in ihrem konfigurierten Charakter
- Vergangene Nachrichten sind im Verlauf einsehbar

---

**US-02.2** – Timer-Status im Blick behalten
> Als Keuschling möchte ich den aktuellen Status meines Timers jederzeit sehen, damit ich weiss wie lange die Session noch dauert.

**Akzeptanzkriterien:**
- Dashboard zeigt Timer (Restzeit oder "Gefrorener Timer")
- Timer-Zustand (laufend / gefroren) ist klar erkennbar
- Letzte Timer-Änderungen sind protokolliert

---

**US-02.3** – Aufgabe erhalten und erledigen
> Als Keuschling möchte ich von der Keyholderin Aufgaben gestellt bekommen und diese bestätigen können, damit die Session abwechslungsreich bleibt.

**Akzeptanzkriterien:**
- Aufgaben erscheinen als Karte im Interface
- Aufgabe kann als erledigt markiert werden (optional mit Text/Foto)
- Bei Erledigung: KI bewertet und vergibt Belohnung/Bestrafung
- Bei Fristüberschreitung: automatische Bestrafung

---

**US-02.4** – Bildverifikation bestehen
> Als Keuschling möchte ich auf Anfrage der Keyholderin ein Foto hochladen, damit sie sich von meiner Disziplin überzeugen kann.

**Akzeptanzkriterien:**
- Verifikationsanfrage erscheint als prominente Nachricht
- Upload-Funktion direkt im Interface
- Optional: Seal-Nummer wird in der Anforderung mitgeteilt
- KI analysiert das Bild und gibt Feedback im Stile der Persona

---

**US-02.5** – Belohnung erhalten
> Als Keuschling möchte ich für gutes Verhalten belohnt werden, damit ich Motivation habe die Regeln einzuhalten.

**Akzeptanzkriterien:**
- Belohnung wird als Event im Interface gemeldet
- Timer-Änderung wird sichtbar aktualisiert
- Keyholderin kommentiert die Belohnung in ihrer Persona

---

**US-02.6** – Vertragsänderung zustimmen
> Als Keuschling möchte ich nachvollziehen können wenn die Keyholderin einen Parameter ändern möchte, und aktiv zustimmen müssen, damit die Bindung des Vertrags gewahrt bleibt.

**Akzeptanzkriterien:**
- KI-initiierte Parameter-Änderungen erscheinen als expliziter Zustimmungsdialog
- Der Nutzer kann zustimmen oder ablehnen
- Bei Zustimmung wird ein Vertrags-Addendum mit Zeitstempel erstellt
- Sicherheitsparameter erscheinen nie in einem solchen Dialog

---

**US-02.7** – Bestrafung akzeptieren
> Als Keuschling muss ich Bestrafungen akzeptieren, damit das Spiel konsequent bleibt.

**Akzeptanzkriterien:**
- Bestrafung wird klar kommuniziert mit Begründung
- Timer-Änderung / Freeze wird sofort angewendet
- Keyholderin kommentiert die Bestrafung in ihrer Persona

---

**US-02.8** – Benachrichtigung erhalten
> Als Keuschling möchte ich Benachrichtigungen erhalten, auch wenn ich die App gerade nicht aktiv nutze, damit mir nichts Wichtiges entgeht.

**Akzeptanzkriterien:**
- Browser Push Notification bei Aufgaben-Deadline
- Push Notification bei Nachrichten der Keyholderin
- Nutzer kann Benachrichtigungen in den Einstellungen konfigurieren

---

### EPIC-03: Sicherheit

**US-03.1** – Ampelsystem nutzen
> Als Keuschling möchte ich jederzeit meinen Zustand signalisieren können, damit die Keyholderin ihre Intensität anpassen kann.

**Akzeptanzkriterien:**
- Drei Buttons (Grün / Gelb / Rot) sind persistent im UI sichtbar
- Grün: "Alles gut" – keine Änderung
- Gelb: Keyholderin reduziert Intensität, fragt nach Wohlbefinden
- Rot: Session wird sofort pausiert, Keyholderin wechselt in Fürsorge-Modus

---

**US-03.2** – Safeword aktivieren
> Als Keuschling möchte ich ein Safeword eingeben können, das die Session sofort und ohne In-Game-Konsequenzen beendet.

**Akzeptanzkriterien:**
- Safeword ist konfigurierbar und prominent erreichbar
- Aktivierung unterbricht die KI-Persona sofort
- Session wird als "beendet (Safeword)" protokolliert
- Kein negativer In-Game-Eintrag

---

**US-03.3** – Emergency Release durchführen
> Als Keuschling muss ich im Notfall eine Session sofort beenden können, auch wenn es vorzeitig ist.

**Akzeptanzkriterien:**
- Emergency-Release-Button ist immer erreichbar
- Vor Ausführung: Pflicht-Begründungs-Eingabefeld (kann nicht leer bleiben)
- Bestätigungsdialog mit klarer Warnung
- Session wird als "Emergency Release" protokolliert
- Begründung wird im Safety-Log gespeichert

---

### EPIC-04: Konfiguration

**US-04.1** – Keyholderin-Persona erstellen
> Als Keuschling möchte ich eine individuelle Keyholderin-Persona definieren, damit die Session meinen Vorstellungen entspricht.

**Akzeptanzkriterien:**
- Name, Persönlichkeitsbeschreibung, Kommunikationsstil konfigurierbar
- Strenge/Freundlichkeit als Skala wählbar
- System-Prompt wird automatisch aus den Eingaben generiert
- Manuelle Anpassung des System-Prompts möglich

---

**US-04.2** – KI-Backend konfigurieren
> Als Keuschling möchte ich wählen können welche KI ich nutze, damit ich die Kontrolle über meine Daten behalte.

**Akzeptanzkriterien:**
- Auswahlmenü für Anbieter (Grok, OpenAI-kompatibel, Ollama)
- Eingabe für API-Endpoint und API-Key
- Modell-Auswahl
- Test-Button mit Verbindungsbestätigung

---

### EPIC-05: Session abschliessen

**US-05.1** – Session regulär beenden
> Als Keuschling möchte ich nach Ablauf der Sperrdauer die Session ordentlich abschliessen und einen Rückblick erhalten.

**Akzeptanzkriterien:**
- Keyholderin kündigt das Ende der Session an
- Zusammenfassung: Dauer, erledigte Aufgaben, Belohnungen/Bestrafungen
- Session wird als "abgeschlossen" markiert
- Verlauf bleibt einsehbar

---

**US-05.2** – Vergangene Sessions einsehen
> Als Keuschling möchte ich vergangene Sessions einsehen, damit ich meine Entwicklung nachverfolgen kann.

**Akzeptanzkriterien:**
- Liste aller abgeschlossenen Sessions
- Kurzübersicht pro Session (Dauer, Persona, Status)
- Detailansicht mit Verlauf, Tasks, Ereignissen

---

## Zukünftige Stories (nach MVP)

| Story | Epic |
|---|---|
| Als realer Keyholder möchte ich Remote-Zugriff auf eine laufende Session haben | Remote-Keyholder |
| Als Keuschling möchte ich Achievements freischalten | Gamification |
| Als Keuschling möchte ich einen Streak sehen | Gamification |
| Als Keuschling möchte ich Aufgaben aus einer Bibliothek wählen lassen | Aufgaben-System |
