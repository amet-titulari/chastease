# UI/UX Anforderungen (MVP)

## Zielbild

Die Anwendung soll modern, responsiv und geraeteuebergreifend nutzbar sein.
Ein Wearer kann eine Session auf dem Smartphone starten und nahtlos auf Tablet oder Desktop fortsetzen und wieder zurueckwechseln.

## UX-Grundprinzipien

- Mobile-first Informationsarchitektur
- Klare visuelle Hierarchie fuer Chat, Sessionstatus und kritische Aktionen
- Konsistente Interaktionsmuster ueber alle Geraeteklassen
- Fokus auf geringe Reibung in Kernaufgaben (Session starten, chatten, kontrollieren)

## Funktionale UX-Anforderungen

- Die Anwendung muss in Deutsch (`de`) und Englisch (`en`) nutzbar sein.
- Spracheinstellung ist nutzerbezogen zu speichern und auf allen Geraeten konsistent anzuwenden.
- Aktive Session ist konto-gebunden und geraeteunabhaengig abrufbar.
- Beim Geraetewechsel wird der letzte konsistente Zustand inkl. Turn-Verlauf geladen.
- Konfliktfaelle (gleichzeitige Eingaben auf mehreren Geraeten) muessen nachvollziehbar aufgeloest werden.
- Kritische Aktionen (z. B. TTLock Open/Close Phase-2) muessen klar, unmissverstaendlich und fehlersicher gefuehrt werden.

## Responsive Anforderungen

- Breakpoints mindestens fuer Smartphone, Tablet, Desktop.
- Chat-Ansicht auf Mobile priorisiert; sekundaere Panels als Drawer/Sheets.
- Lesbarkeit und Touch-Targets nach gaengigen Accessibility-Standards.

## Performance-Anforderungen fuer UX

- Chat UI reagiert sofort auf Eingabe (optimistische UI zulaessig).
- Zeit bis zur sichtbaren Serverantwort im Chat soll minimiert werden.
- Integrations-/Agentenaktionen duerfen laenger dauern, muessen aber transparenten Status anzeigen.

## Accessibility und Trust

- Tastaturbedienung auf Desktop
- ausreichende Kontraste und skalierbare Typografie
- klare Kennzeichnung von KI-Antworten, KI-Aktionen und Systemmeldungen
- einsehbare Historie und Audit-Hinweise fuer sicherheitsrelevante Ereignisse
