# Fantasy NBA v2 – Produkt-Spezifikation

Dieses Dokument beschreibt präzise, welche Daten gezogen und verarbeitet werden und welche Features die Website
haben soll. Basis ist Feature-Parität mit `fantasy_nba` v1 plus den in `docs/decisions/0001-serverless-architecture.md`
beschlossenen strukturellen Verbesserungen. Änderungen gegenüber v1 sind explizit als **[NEU/v2]** markiert.

---

## 1. Datenquellen (was wird gezogen)

Alle Daten kommen über das Python-Paket `nba_api` (inoffizielle, aber verbreitete Wrapper um die
stats.nba.com-Endpunkte) und laufen ausschließlich in `pipeline/` (siehe ADR 0001) — nie im Web-Request-Pfad.

| Quelle | Endpoint/Methode | Frequenz | Zweck |
|---|---|---|---|
| Spieler-Stammdaten | `CommonAllPlayers` (aktuelle Saison) | 1×/Saison bzw. bei Roster-Änderungen | `PERSON_ID`, `DISPLAY_FIRST_LAST`, `TEAM_ID`, `TEAM_NAME` — Basis-Spielerliste |
| Game Logs pro Spieler | `LeagueGameLog` (player-level, ganze Liga auf einmal, nicht pro Spieler einzeln — v1 nutzte anfangs `PlayerGameLog` pro Spieler, was sehr langsam/rate-limit-anfällig war) | **täglich** (inkrementell, nur neue Spiele seit letztem Lauf) | Rohdaten für alle Ratings: `SEASON_ID, Player_ID, Game_ID, GAME_DATE, MATCHUP, WL, MIN, FGM, FGA, FG3M, FG3A, FTM, FTA, OREB, DREB, REB, AST, STL, BLK, TOV, PF, PTS, PLUS_MINUS` |
| Spielplan (Schedule) | Saison-Spielplan (Visitor/Home/Datum je Team) | 1×/Saison, ggf. bei Terminverschiebungen aktualisieren | Grundlage für "Spiele pro Woche je Team" → Wochen-Ratings |
| Spielerpositionen (NBA) | `CommonPlayerInfo` pro Spieler | selten (ändert sich kaum während der Saison) | Rohposition (Guard/Forward/Center/Kombinationen) |
| **[NEU/v2]** Fantasy-Positionen | abgeleitet aus NBA-Position (siehe Verarbeitung unten) | bei jedem Positions-Update | Standard-Fantasy-Slots: PG, SG, SF, PF, C (Mehrfach-Eligibility möglich, z. B. Guard → PG+SG) |

**Wichtiger Unterschied zu v1:** In v1 lief der tägliche Pull entweder als Render Cron Job ODER als GitHub Action mit
Commit zurück ins Repo — zwei parallele, halb genutzte Wege. In v2 gibt es **nur einen Weg**: die tägliche
GitHub Action schreibt direkt nach Supabase (siehe ADR 0001).

---

## 2. Datenverarbeitung (Rating-Engine)

Migriert und bereinigt aus `fantasy_nba/nba_project/fantasy_nba/{ratings,games_played,helpers,weeks}.py`.

### 2.1 Saison-Aggregation
Nur die **aktuelle Saison** wird verwendet (kein Blend mit Vorjahresdaten in v1 — das war zwar im Code vorbereitet,
aber deaktiviert). Pro Spieler werden alle Game-Log-Zeilen der laufenden Saison gemittelt (Mean je numerischer Spalte).

### 2.2 9-Kategorien-Ratings (Standard-Roto/9-Cat-Format)
Kategorien: `PTS, REB, AST, FG%, FT%, 3PTM, BLK, STL, TOV`

- **FG%/FT% werden NICHT als reine Prozentwerte gewertet**, sondern als "Net"-Wert:
  `FGN = FGM − (FGA − FGM)` (Treffer minus Fehlwürfe) bzw. analog `FTN` für Freiwürfe.
  Das gewichtet Volumen mit — ein Spieler mit 90 % FG bei 2 Versuchen schlägt nicht automatisch einen
  50-%-Spieler mit 20 Versuchen.
- Alle 9 Rohwerte werden **linear auf 0–100 skaliert** (`Wert / Max-Wert-der-Liga × 100`), nicht z-normiert.
- `TOV` wird invertiert (`100 − normiert`), da weniger Turnover besser ist.

### 2.3 Verfügbarkeits-Gewichtung ("Performance Rating")
`availability_score = gespielte_Spiele_des_Spielers / gespielte_Spiele_seines_Teams` (aktuelle Saison).
Ein Spieler, der wegen Verletzung viele Teamspiele verpasst hat, bekommt dadurch einen niedrigeren Score.

- `Total_Rating` = Summe aller 9 Kategorie-Ratings, neu auf 0–100 normiert = **"Overall Rating"**
- `Total_Available_Rating` = `Total_Rating × availability_score`, neu normiert = **"Performance Rating"**
- `Combined_Rating` = Mittelwert aus beiden, neu normiert = **"Combined Rating"**

### 2.4 Punt-Varianten **[v2: ADR 0002]**
Die Pipeline speichert nur die 9 rohen Kategorie-Ratings + `availability_score` pro Spieler — **keine**
vorberechneten Punt-Kombinationen mehr (v1 berechnete alle 45 1er/2er-Kombinationen × 3 Rating-Typen vorab als
135 Spalten). Punt-adjustierte Overall-/Performance-/Combined-Ratings werden stattdessen zur Laufzeit im Frontend
berechnet (verbleibende Kategorien summieren → gegen Max der angezeigten Spieler neu skalieren →
`availability_score` einrechnen). Dadurch sind bis zu **4** gleichzeitig geputtete Kategorien möglich (v1: 2),
ohne Pipeline- oder Schema-Änderung. Details/Begründung: `docs/decisions/0002-punt-ratings-on-demand.md`.

### 2.5 Wochen-Ratings **[Zurückgestellt, ADR 0003 — nicht Teil des v2-Erstrelease]**
Pro ISO-Kalenderwoche: `week_rating = Total_Rating × (Spiele_des_Teams_diese_Woche / Max_Spiele_eines_Teams_diese_Woche)`.
Zeigt, welche Spieler in einer bestimmten Woche wegen eines vollen Spielplans ihres Teams besonders wertvoll sind
(z. B. für Streaming/Waiver-Entscheidungen).

### 2.6 Fantasy-Positionen-Mapping
NBA-Rohposition → Fantasy-Slots (Mehrfach-Eligibility):
`Guard → [PG, SG]`, `Forward-Guard/Guard-Forward → [SG, SF]`, `Forward → [SF, PF]`,
`Forward-Center/Center-Forward → [PF, C]`, `Center → [C]`.

### 2.7 Team-Positions-Coverage
Greedy-Zuordnung der Roster-Spieler auf die 8 Slots `PG, SG, G, SF, PF, F, C, C` (G = PG-oder-SG, F = SF-oder-PF),
Ausgabe: welche Slots noch fehlen. Berücksichtigt Mehrfach-Eligibility.

**[NEU/v2]** Diese Zuordnung ist aktuell ein reiner Greedy-Algorithmus (v1-Kommentar weist selbst darauf hin, dass
er suboptimal sein kann). Für v2 evaluieren, ob eine echte bipartite Zuordnung (z. B. Ungarischer Algorithmus)
lohnt — niedrige Priorität, kein Blocker.

---

## 3. Features der Website

### 3.1 Ratings-Tabelle (Kernfeature, Startseite)
- Top ~200 Spieler nach `Total_Rating`, alle Kategorie-Ratings + Overall/Performance/Combined Rating, Fantasy-Position(en).
- Sortierbar durch Klick auf Spaltenkopf (auf-/absteigend), Statusfilter (Alle / Im Team / Verfügbar / Nicht verfügbar / Verletzt / Gesund).
- Heatmap-Färbung (rot→grün je Kategorie-Wert) und Tier-Färbung (grau→lila je Rating-Höhe), beide optional zuschaltbar.
- Team-Durchschnittszeile oben angeheftet, wenn ein aktives Team mit Spielern existiert.
- Anzeige "Daten zuletzt aktualisiert am [Datum]".
- **[NEU/v2]** Sortieren/Filtern **client-seitig ohne Reload** (v1 macht dafür einen vollen Seiten-Reload +
  Server-Session-Update — UX-Downgrade, den v2 beheben soll).

### 3.2 Spieler-Aktionen (pro Zeile)
- Status setzen: Im Team / Verfügbar / Nicht verfügbar (fließt in Team-Durchschnitt & Coverage ein).
- Verletzt markieren (eigener Filter "Verletzt/Gesund").
- Highlighten (visuelle Markierung, rein persönliche Notiz).
- Bis zu 2 Spieler für Vergleich auswählen → Stat-Vergleichsansicht (9 Kategorien, z. B. als Radar-Chart).
- **[NEU/v2]** In v1 sind Highlight/Verletzt/Vergleich nur in der Server-Session gespeichert (weg bei Cookie-Löschung,
  nicht geräteübergreifend). In v2 in Supabase pro Nutzer persistieren.

### 3.3 Team-Verwaltung (`/team`)
- Mehrere Teams pro Nutzer anlegen/umbenennen/löschen, genau eines als "aktiv" markieren.
- Roster-Ansicht des aktiven Teams mit Ratings + Team-Durchschnitt + "fehlende Positionen"-Text.

### 3.4 Draft-Modus
- Beim ersten Öffnen automatische Draft-Reihenfolge nach `Total_Rating` absteigend.
- Nutzer kann Picks manuell umsortieren (hoch/runter oder direkte Position setzen) → persönliches Draft-Cheat-Sheet.
- `Draft_Pos`-Spalte in der Ratings-Tabelle sortierbar, sobald ein Team aktiv ist.

### 3.5 Punt-Tool (`/punt`)
- Bis zu 4 Kategorien als "geputtet" markieren (bewusst ignoriert für die Team-Strategie, gängiges 9-Cat-Konzept;
  v1 erlaubte nur 2 — siehe ADR 0002).
- Ratings-Tabelle zeigt danach automatisch die entsprechende Punt-Rating-Variante (Overall/Performance/Combined
  ohne die geputteten Kategorien), berechnet on-demand im Frontend statt vorab in der Pipeline.

### 3.6 Anzeige-Einstellungen (`/punt`, "Settings"-Bereich)
- Heatmap-Färbung an/aus, Tier-Färbung an/aus.

### 3.7 Auth
- Registrierung/Login/Logout.
- **[NEU/v2]** Supabase Auth statt Django-Sessions (siehe ADR 0001).

### 3.8 "Breakdown"-Seite
- In v1 aktuell nur ein Platzhalter-Template ohne Inhalt. **[NEU/v2]** Sinnvoll ausbauen: kurze Erklärung der
  Rating-Methodik (Abschnitte 2.1–2.7 oben, für Endnutzer verständlich aufbereitet) statt Leerseite.

### 3.9 Betriebs-/Health-Endpunkte
- v1 hat einen Health-Check-Endpoint (nötig für Render) und einen selbstgebauten `/admin_reset/`-Endpoint als
  Workaround für fehlenden Shell-Zugriff im Render Free Tier.
- **[NEU/v2]** Entfällt so in dieser Form: Supabase-Dashboard übernimmt DB-Verwaltung, Vercel braucht keinen
  eigenen Health-Check-Workaround. Prüfen, ob überhaupt noch ein Analogon gebraucht wird.

---

## 4. Entschieden (vormals "Offene Fragen")

- **Punt-Varianten-Speicherung:** on-demand im Frontend berechnet, nicht vorberechnet in Supabase.
  → `docs/decisions/0002-punt-ratings-on-demand.md`
- **Anzahl puntbarer Kategorien:** bis zu 4 (v1: 2), rein UI-seitig konfigurierbar dank on-demand-Berechnung.
  → `docs/decisions/0002-punt-ratings-on-demand.md`
- **Wochen-Ratings:** zurückgestellt, nicht Teil des v2-Erstrelease (in v1 ohnehin nirgends in der UI verwendet).
  → `docs/decisions/0003-weekly-ratings-deferred.md`

## 5. Backlog (bewusst nicht im Erstrelease)

- Wochen-Ratings als sichtbares "Streaming/Waiver-Helfer"-Feature (siehe ADR 0003).
- Team-Positions-Coverage über einen echten Zuordnungs-Algorithmus (z. B. bipartites Matching) statt Greedy-Heuristik.
