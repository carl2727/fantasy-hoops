# pipeline/

Eigenstaendiges Python-Paket, das taeglich per GitHub Action (`.github/workflows/daily-pipeline.yml`) laeuft:
NBA-Daten abrufen, Ratings berechnen, nach Supabase schreiben. Laeuft bewusst NICHT im Webserver-Prozess
(siehe `docs/decisions/0001-serverless-architecture.md`).

## Lokal ausfuehren

```bash
cd pipeline
pip install -r requirements.txt
cp .env.example .env   # dann echte Werte eintragen, siehe docs/environment.md
cd ..
python -m pipeline.main
```

## Module

- `config.py` – Konstanten (Saison, Team-ID-Mapping, Positions-Mapping), Env-Var-Zugriff
- `nba_data.py` – alle `nba_api`-Aufrufe (Spielerliste, Saison-Game-Logs, Spieler-Positionen)
- `positions.py` – NBA-Rohposition -> Fantasy-Slots (PG/SG/SF/PF/C)
- `ratings_engine.py` – reine Rating-Berechnung, keine I/O (siehe product-spec.md Abschnitt 2)
- `supabase_io.py` – alles, was mit Supabase spricht (Service-Role-Key, umgeht RLS bewusst)
- `main.py` – Orchestrierung, Einstiegspunkt

## Wichtig

Diese Pipeline wurde noch **nicht gegen ein echtes Supabase-Projekt/live nba_api getestet** (das Environment,
in dem sie geschrieben wurde, hat keinen Internetzugriff). Vor dem ersten produktiven Cron-Lauf: einmal manuell
lokal (`python -m pipeline.main`) oder ueber `workflow_dispatch` in GitHub Actions ausfuehren und die Logs pruefen.
