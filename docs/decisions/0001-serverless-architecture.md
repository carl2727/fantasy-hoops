# 0001 – Serverless-Architektur statt dauerlaufender Django-Server

**Status:** Accepted (2026-08-02)

## Kontext

`fantasy_nba` v1 lief als Django-App auf Render (Free Tier), mit SQLite lokal / Postgres in Produktion.
Beobachtete Probleme:

- Ratings wurden beim Import von `ratings.py` (also beim Start des Django-Prozesses) berechnet. Neue Daten aus
  dem täglichen `nba_api`-Pull wurden erst nach einem Neustart/Redeploy sichtbar.
- Zwei parallele, halb genutzte Lösungen für den täglichen Datenpull (Render Cron Job vs. GitHub Action, die CSVs
  zurück ins Repo committed) – Quelle für Verwirrung.
- Render Free Tier: Cold Starts, Health-Check-Loop-Probleme, pandas/numpy-Wheel-Kompatibilitätsprobleme, kein
  Shell-Zugriff (führte zu einem selbstgebauten `/admin_reset/`-Endpoint als Workaround).
- Kostenlose "immer laufende" Python-Server-Hosts sind 2026 kaum noch verfügbar (Heroku/Fly/Render Free stark
  eingeschränkt oder abgeschafft).
- UI: Sortieren/Filtern lief über Query-Parameter + vollständigen Seiten-Reload, kein reaktives Interface.

## Entscheidung

Architektur in zwei entkoppelte Teile aufsplitten:

1. **Datenpipeline** (`pipeline/`): eigenständiges Python-Paket, läuft ausschließlich als tägliche GitHub Action.
   Zieht Daten über `nba_api`, berechnet Ratings, schreibt Ergebnis nach Supabase (Postgres).
2. **Frontend** (`app/`): Next.js, hostet rein lesend/interaktiv auf Vercel (Free). Nutzt Supabase (Auth + DB)
   für Login, Teams, Draft Picks — kein eigener Applikationsserver, der dauerhaft laufen muss.

Damit ist die Datenaktualität nicht mehr an einen Webserver-Neustart gekoppelt, und das Hosting bleibt dauerhaft
kostenlos im Hobby-Rahmen, da nichts "always-on" bezahlt werden muss außer den Free Tiers von Vercel/Supabase.

## Verworfene Alternativen

- **Django behalten, nur Frontend mit htmx modernisieren, Hosting zu PythonAnywhere/Fly.io wechseln.**
  Geringerer Migrationsaufwand, aber das Grundproblem (dauerlaufender Server ohne verlässliches Free-Tier)
  bleibt bestehen. Verworfen, weil das Hosting-Ziel ("möglichst kostenlos, dauerhaft") damit nicht robust erreicht wird.
- **Alles als eine monolithische Next.js-App inkl. Datenpull in Vercel Cron Functions.**
  Möglich, aber Vercel Cron Functions haben auf dem Free Plan Laufzeit-/Frequenz-Limits, die für
  `nba_api`-Aufrufe + pandas-Berechnung eng werden können. GitHub Actions bietet mehr Laufzeit-Puffer und ist
  vom Hosting-Anbieter der App unabhängig.

## Konsequenzen

- Zwei Repos-Teile/Sprachen (TypeScript-Frontend, Python-Pipeline) statt einer Codebasis — höhere Komplexität,
  aber sauberere Trennung von Concerns.
- Rating-Berechnung muss vollständig ohne Django-Abhängigkeiten lauffähig sein (siehe Offene Punkte in `CLAUDE.md`).
- Supabase wird zur zentralen Abhängigkeit für Auth + Daten — Vendor-Lock-in ist ein bewusst akzeptierter Trade-off
  gegen Entwicklungsgeschwindigkeit und Kosten.
