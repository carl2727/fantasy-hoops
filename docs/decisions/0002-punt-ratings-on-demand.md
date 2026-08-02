# 0002 – Punt-Ratings on-demand berechnen statt vorzuberechnen

**Status:** Accepted (2026-08-02)

## Kontext

v1 berechnet in `ratings.py` für jede 1er- und 2er-Kombination der 9 Kategorien (45 Kombinationen) alle drei
Rating-Varianten (Overall/Performance/Combined) im Voraus und speichert sie als eigene Spalten — 135 zusätzliche
Spalten in der Ratings-Tabelle. Dadurch ist die Anzahl gleichzeitig "puntbarer" Kategorien in v1 auf 2 begrenzt
(die UI bietet nur `punt_category_1`/`punt_category_2`), da jede weitere Kategorie die Kombinatorik stark wachsen
lässt (3 Kategorien → 129 Kombinationen, beliebig viele → 2⁹ = 512).

## Entscheidung

Die Pipeline (`pipeline/`) speichert pro Spieler nur noch die **9 rohen Kategorie-Ratings** (0–100 skaliert) plus
den `availability_score` in Supabase — keine vorberechneten Punt-Varianten mehr.

Punt-adjustierte Overall-/Performance-/Combined-Ratings werden **zur Laufzeit** berechnet (Frontend oder eine
dünne API-Route): verbleibende (nicht geputtete) Kategorien summieren, gegen das Maximum der aktuell angezeigten
Spieler neu auf 0–100 skalieren, mit `availability_score` multiplizieren/mitteln — exakt dieselbe Formel wie in
v1, nur zur Anzeigezeit statt vorab.

Dadurch wird die Anzahl gleichzeitig puntbarer Kategorien auf **bis zu 4** erhöht (siehe auch ADR-Kontext: v1 hatte
2), ohne dass das an der Pipeline oder am Supabase-Schema etwas ändert — es ist reine Filterlogik im Frontend.
Der Cap ist rein UI-seitig konfiguriert und jederzeit ohne Schema-Migration anpassbar.

## Verworfene Alternativen

- **Wide-Table mit allen Punt-Spalten (wie v1):** verworfen — unflexibel bei jeder Erweiterung (Schema-Migration
  pro neuer Kombination), unübersichtlich (135+ Spalten).
- **Normalisierte `punt_ratings`-Tabelle mit vorberechneten Zeilen pro Kombination:** verworfen — unnötiger
  Vorberechnungs- und Speicheraufwand, wenn die Berechnung zur Laufzeit trivial und schnell ist (Millisekunden
  bei ~200 angezeigten Spielern).

## Konsequenzen

- Rating-Engine in `pipeline/` wird einfacher: keine Kombinatorik-Logik mehr, nur noch die 9 Basis-Ratings +
  Verfügbarkeits-Score.
- Die Normalisierungs-/Punt-Formel muss im Frontend (bzw. einer gemeinsam genutzten Utility-Funktion) korrekt
  reimplementiert werden — als eine getestete, dokumentierte Funktion, nicht zweimal unabhängig voneinander in
  Python und TypeScript gepflegt, um Drift zu vermeiden.
- Frontend braucht für die angezeigten Spieler die rohen 9 Kategorie-Werte statt nur fertiger Ratings — minimal
  mehr Daten pro Request (~200 Spieler × 9 Zahlen), vernachlässigbar.
