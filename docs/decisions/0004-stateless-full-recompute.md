# 0004 – Täglicher voller Neuaufbau statt inkrementellem Game-Log-Abruf

**Status:** Accepted (2026-08-02)

## Kontext

v1 (`update_nba_game_logs.py`) holt bei jedem Lauf nur Spiele seit dem letzten gespeicherten Datum in der
lokalen CSV (inkrementeller Abruf), um die API zu schonen. Das setzt voraus, dass zwischen zwei Läufen ein
persistenter Zustand existiert (die CSV-Datei), der von Lauf zu Lauf fortgeschrieben wird.

Beim Bau von `pipeline/` (GitHub Action, jeder Lauf startet in einem frischen, zustandslosen Container) fiel auf:
Der `LeagueGameLog`-Endpunkt liefert die **gesamte Liga für eine beliebige Zeitspanne in einem einzigen
API-Call** — ob man `date_from` auf "seit letztem Lauf" oder auf "Saisonstart" setzt, kostet exakt einen Request.
Der inkrementelle Abruf spart hier also keine API-Calls, nur Zeilen in der Response (marginal).

## Entscheidung

`pipeline/nba_data.fetch_season_game_logs()` holt bei **jedem** täglichen Lauf die kompletten Game-Logs der
laufenden Saison (Saisonstart bis heute) in einem Call, und `ratings_engine.compute_ratings()` berechnet daraus
alle Ratings komplett neu. Es wird **kein** roher Game-Log-Datenbestand zwischen den Läufen persistiert (weder
als Datei noch als eigene Supabase-Tabelle) — `ratings` in Supabase wird bei jedem Lauf per Upsert + Delete-Sync
komplett auf den heutigen Stand gebracht (siehe `supabase_io.sync_ratings()`).

## Verworfene Alternativen

- **Inkrementeller Abruf wie in v1, Rohdaten in einer neuen `game_logs`-Supabase-Tabelle persistieren:**
  verworfen — zusätzliche Tabelle und Zustand, ohne dass es API-Calls spart (siehe Kontext oben), und mit dem
  Risiko, dass ein fehlgeschlagener Lauf den "letzten bekannten Stand"-Zeiger inkonsistent zurücklässt.
- **Rohdaten wie im alten GitHub-Action-Workflow als CSV zurück ins Repo committen:** verworfen — genau die
  Vermischung von Datenpipeline und Versionskontrolle, die ADR 0001 bewusst auflösen wollte.

## Konsequenzen

- Die Pipeline ist **selbstheilend**: Schlägt ein Lauf fehl oder wird ein Tag ausgelassen, berechnet der nächste
  erfolgreiche Lauf trotzdem den korrekten, vollständigen Stand — kein Nachholen fehlender Zwischenschritte nötig.
- Etwas mehr Rechenaufwand pro Lauf (volles `groupby`/Normalisierung über die Saison statt nur neue Zeilen),
  bei ~500 Spielern und wenigen tausend Zeilen pro Saison für Pandas vollkommen vernachlässigbar.
- `ratings` in Supabase enthält nur Spieler mit mindestens einem Spiel in der laufenden Saison — keine künstliche
  Begrenzung auf "Top 200" (siehe Korrektur in `product-spec.md` Abschnitt 3.1: der Top-200-Cap aus v1 war
  totes Code, wurde berechnet aber nie tatsächlich angewendet).
