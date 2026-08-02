# Fantasy Hoops

Neuaufbau des bestehenden `fantasy_nba`-Projekts (9-Kategorien Fantasy-Basketball-Ratings & Team-/Draft-Tool).
Ziel: kostenlos/günstig hostbar, tägliche NBA-API-Daten, modernes UI.

## Doku-Übersicht

- `docs/decisions/` – ADRs (Architektur-Entscheidungen, Kontext, verworfene Alternativen)
- `docs/product-spec.md` – Datenquellen, Rating-Berechnung und Feature-Liste der Website im Detail
- `docs/schema.md` – Supabase-Tabellenschema mit Begründung; ausführbares DDL in `supabase/schema.sql`

## Architektur (siehe docs/decisions/0001-serverless-architecture.md)

- **`app/`** – Next.js (TypeScript, Tailwind/shadcn) Frontend, gehostet auf Vercel (Free).
- **`pipeline/`** – Eigenständiges Python-Paket, das täglich per GitHub Action läuft: zieht Game Logs über `nba_api`,
  berechnet die Ratings (Min-Max-Normalisierung pro Kategorie + Verfügbarkeits-Gewichtung + Punt-Kombinationen)
  und schreibt sie nach Supabase. Läuft NICHT im Webserver-Prozess.
- **Supabase** (Postgres + Auth) – einzige Datenquelle für Frontend und Pipeline. Tabellen u. a.: `players`,
  `ratings`, `teams`, `team_players`, `draft_picks`.

## Warum dieser Weg (Kurzfassung)

Das alte Projekt (Django auf Render Free) hatte drei Kernprobleme:
1. Ratings wurden beim Start des Django-Prozesses berechnet → neue Daten brauchten einen Redeploy.
2. Kein "für immer kostenloses" Hosting für einen dauerlaufenden Python-Server mehr verfügbar (Render/Fly/Heroku
   Free sind inzwischen alle eingeschränkt).
3. UI war Full-Page-Reload-basiert (Sortierung/Filter über Query-Params + Session).

Lösung: Datenpipeline komplett vom Webserver entkoppeln (läuft in GitHub Actions, nicht im Request-Pfad),
Frontend wird dadurch rein lesend/serverless und kann auf Vercel/Supabase Free laufen.

## Konventionen

- Architektur-Entscheidungen werden als ADR unter `docs/decisions/NNNN-titel.md` festgehalten, BEVOR sie umgesetzt
  werden. Verworfene Alternativen gehören mit rein, damit sie nicht in einer späteren Session neu diskutiert werden.
- Diese Datei (`CLAUDE.md`) hält nur den aktuellen Stand fest (Zusammenfassung), nicht die volle Historie/Begründung
  — die liegt in den ADRs.
- Commit-Stil: kurze, imperative Commit-Messages (z. B. "Add rating normalization", nicht "Added").
- Secrets (`.env`, Supabase Keys) niemals committen — siehe `.gitignore`.

## Offene Punkte

- [ ] Projektordner von `fantasy-nba-v2` auf `fantasy-hoops` umbenennen (aktuell durch offenes VS-Code-Fenster
      gesperrt — VS Code schließen, dann Ordner umbenennen und in VS Code neu öffnen)
- [x] Supabase-Schema final definieren (`docs/schema.md`, `supabase/schema.sql`)
- [ ] Supabase-Projekt anlegen und `supabase/schema.sql` ausführen
- [ ] Rating-Engine aus altem `fantasy_nba`-Projekt nach `pipeline/` migrieren
- [ ] GitHub Action für täglichen Datenpull aufsetzen
- [ ] Next.js Grundgerüst mit Ratings-Tabelle (Read-only, Feature-Parität zu v1)
