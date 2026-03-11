# Benutzeranleitung – Chastease

Diese Anleitung erklärt Schritt für Schritt, wie du Chastease einrichtest und nutzt.

---

## Inhaltsverzeichnis

1. [Registrierung & Login](#1-registrierung--login)
2. [Ersteinrichtung (Onboarding)](#2-ersteinrichtung-onboarding)
3. [Dashboard](#3-dashboard)
4. [Neue Session starten](#4-neue-session-starten)
5. [Play-Ansicht – Übersicht](#5-play-ansicht--übersicht)
6. [Chat mit der Keyholderin](#6-chat-mit-der-keyholderin)
7. [Aufgaben & Aktionskarten](#7-aufgaben--aktionskarten)
8. [Bildverifikation](#8-bildverifikation)
9. [Sicherheitssystem (Ampel, Safeword, Notfall)](#9-sicherheitssystem-ampel-safeword-notfall)
10. [Hygiene-Öffnung](#10-hygiene-öffnung)
11. [Einstellungen-Drawer](#11-einstellungen-drawer)
12. [Session History & Export](#12-session-history--export)
13. [Verträge](#13-verträge)
14. [Multi-Device-Nutzung](#14-multi-device-nutzung)

---

## 1. Registrierung & Login

Öffne die App im Browser (Standard: `http://<server-ip>:8000`).

- **Registrieren**: Klicke auf „Registrieren", gib einen Benutzernamen (mind. 3 Zeichen) und ein Passwort (mind. 8 Zeichen) ein. Danach wirst du automatisch eingeloggt und zur Ersteinrichtung weitergeleitet.
- **Einloggen**: Gib Benutzername und Passwort ein. Dein Session-Token bleibt 30 Tage gültig, solange du den Browser nicht schließt oder abmeldest. Du kannst dich auf mehreren Geräten gleichzeitig einloggen, ohne gegenseitig abgemeldet zu werden.
- **Abmelden**: Im Dashboard oben rechts → „Abmelden".

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

Das Dashboard (`/`) ist deine Startseite nach dem Login.

- **Aktive Session**: Falls eine Session läuft, siehst du Status und Verbleibzeit. Klicke auf „Zur Session" um zur Play-Ansicht zu wechseln.
- **Neue Session starten**: Direkter Einstiegsbutton.
- **Schnellübersicht**: Letzte Sessions, offene Tasks, Systemstatus.

---

## 4. Neue Session starten

1. Klicke auf „Neue Session starten" im Dashboard oder navigiere zu `/experience`.
2. Wähle oder bestätige die Persona-Auswahl.
3. Wähle die Sperrdauer (zufällig oder fix).
4. Schließe den digitalen Vertrag ab – er dokumentiert die Vereinbarungen für diese Session.
5. Nach dem Signieren startet die Session und du gelangst zur Play-Ansicht.

---

## 5. Play-Ansicht – Übersicht

Die Play-Ansicht (`/play`) ist die Hauptoberfläche während einer aktiven Session.

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

- **Header links**: Persona-Name und Countdown (Zeit bis Session-Ende oder bis nächstem Ereignis).
- **Tasks-Badge**: Zeigt die Anzahl offener Aufgaben. Rotes Badge = dringende Aufgaben vorhanden.
- **Zahnrad ⚙**: Öffnet den Einstellungen-Drawer.
- **Chat-Timeline**: Alle Nachrichten chronologisch; Aktionskarten erscheinen am Ende.

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
│ 📋 Aufgaben-Titel                    │
│ Beschreibung der Aufgabe…            │
│                                      │
│ [✓ Erledigt] [✗ Fehlgeschlagen]      │
│ oder: [📷 Verifizieren]              │
└──────────────────────────────────────┘
```

| Button | Aktion |
|---|---|
| **Erledigt** | Markiert den Task als abgeschlossen; Belohnung (z.B. Zeitabzug) wird angewendet. |
| **Fehlgeschlagen** | Markiert den Task als nicht erfüllt; Strafe (z.B. Zeitverlängerung) wird angewendet. |
| **Verifizieren** | Öffnet die Foto-Verifikation (nur wenn der Task Verifikation erfordert). |

Das **Tasks-Dropdown** im Header (über das Badge erreichbar) zeigt alle Aufgaben in einer read-only Übersicht.

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

**Hinweis:** Bilder werden nur auf dem Server gespeichert, nicht im Browser-Cache oder der Galerie.

---

## 9. Sicherheitssystem (Ampel, Safeword, Notfall)

Das Sicherheitssystem ist jederzeit verfügbar und überschreibt immer den normalen Session-Ablauf.

### Ampelsystem
Drücke im Einstellungen-Drawer (⚙) oder über die schnellen Ampel-Buttons:

| Farbe | Bedeutung | KI-Reaktion |
|---|---|---|
| 🟢 **Grün** | Alles in Ordnung | Normal |
| 🟡 **Gelb** | Unwohl / leichte Bedenken | Wechselt in fürsorglich-sorgenden Ton |
| 🔴 **Rot** | Stopp – sofortiger Rückzug | Session pausiert; KI deeskaliert aktiv |

### Safeword
Im Drawer → „Safeword ausrufen". Die Session wird sofort in den roten Modus versetzt und protokolliert.

### Notfallentlassung
Im Drawer → „Notfall-Entsperren". Beendet die Session sofort und erstellt einen vollständigen Safety-Log-Eintrag. Dieser Schritt ist **irreversibel**.

---

## 10. Hygiene-Öffnung

Eine Hygiene-Öffnung erlaubt eine zeitlich begrenzte Entsperrung für Reinigungszwecke.

1. ⚙ Drawer → „Hygiene-Öffnung beantragen".
2. Die Dauer wird aus deinem Kontingent abgezogen (konfigurierbar im Vertrag).
3. Während der Öffnung läuft ein Countdown.
4. Klicke „Wieder verschließen" wenn du fertig bist – oder warte bis der Timer abläuft.

---

## 11. Einstellungen-Drawer

Erreichbar über das ⚙-Symbol im Header oder per Swipe (mobile).

Inhalte:
- **Session-Info**: Aktueller Status, Sperr-Ende, Persona
- **Hygiene-Öffnung**: Kontingent und Beantragung
- **Ampel-Status**: Schneller Zugriff auf Gelb/Rot
- **Safeword & Notfall**: Direkte Auslösung
- **Persona wechseln**: Keyholderin während laufender Session anpassen

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

## 14. Multi-Device-Nutzung

Du kannst dich auf mehreren Geräten (z.B. Handy + Tablet) gleichzeitig einloggen. Beide Geräte nutzen dasselbe Session-Token und bleiben verbunden – ein neues Login meldet dich **nicht** auf anderen Geräten aus.

**Empfehlung:** Nutze denselben Browser-Tab nicht auf zwei Geräten gleichzeitig, da der WebSocket-Stream pro Tab verwaltet wird.

---

## Datenschutz & Sicherheit

- Alle Daten bleiben auf deinem lokalen Server – keine Cloud, kein Tracking.
- Verifikationsbilder werden ausschließlich im `data/media/`-Verzeichnis auf dem Server gespeichert.
- Der Server sollte **nicht direkt ins Internet** exponiert werden. Nutze VPN (z.B. WireGuard, Tailscale) für externen Zugriff.
- Das Admin-Secret (`CHASTEASE_ADMIN_SECRET`) in der `.env`-Datei schützt sensible Steuer-Endpunkte.
