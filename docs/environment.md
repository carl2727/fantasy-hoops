# Umgebungsvariablen / Secrets

Übersicht, welche Zugangsdaten wo herkommen, wo sie gebraucht werden und wo sie gespeichert werden — damit das
nicht bei jeder Session neu zusammengesucht werden muss.

### Für `app/` (Next.js) — lokal `.env.local`, produktiv Vercel Env Vars

| Variable | Herkunft (Supabase Dashboard) | Sichtbarkeit |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Project Settings → API → Project URL | öffentlich unbedenklich |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` (aka "publishable key") | Project Settings → API Keys → "anon public" / "publishable" | öffentlich unbedenklich — durch RLS abgesichert (siehe `docs/schema.md`) |

Das `NEXT_PUBLIC_`-Präfix ist Next.js-Konvention (macht die Variable im Browser verfügbar) — hat nichts mit
Supabase selbst zu tun.

### Für `pipeline/` (GitHub Action) — GitHub Repo → Settings → Secrets and variables → Actions

| Name | Typ | Herkunft (Supabase Dashboard) | Sichtbarkeit |
|---|---|---|---|
| `SUPABASE_URL` | Variable (nicht geheim) | Project Settings → API → Project URL | öffentlich unbedenklich |
| `SUPABASE_SERVICE_ROLE_KEY` (aka "secret key") | **Secret** | Project Settings → API Keys → "service_role" / "secret" — **eigener Eintrag, nicht die publishable key von oben** | **GEHEIM** — niemals committen, nur als GitHub Actions Secret hinterlegen |

## Wo speichern

- **Lokale Entwicklung:** `.env.local` in `app/` bzw. `.env` in `pipeline/` — beide bereits über die Wurzel-
  `.gitignore` (`.env*`) ausgeschlossen.
- **Produktion (Next.js):** Vercel Project Settings → Environment Variables.
- **Pipeline (GitHub Action):** GitHub Repo → Settings → Secrets and variables → Actions → "New repository secret".
  Setzt voraus, dass ein GitHub-Remote für dieses Repo existiert (siehe `CLAUDE.md`, aktuell noch nicht angelegt).

## Direkte Postgres-Connection-String

Supabase zeigt im Dashboard auch eine direkte `postgresql://...`-Connection-String an. Für `pipeline/` empfehlen
wir stattdessen den `supabase-py`-Client mit dem `SUPABASE_SERVICE_ROLE_KEY` statt einer rohen psycopg2/asyncpg-
Verbindung: Supabase rät bei kurzlebigen Verbindungen (wie einem GitHub-Actions-Runner, der pro Lauf neu startet)
eher zum Pooler oder Client-SDK statt zur direkten Verbindung, u. a. wegen möglicher IPv6-Connectivity-Probleme
aus manchen CI-Umgebungen. Die DB-Passwort/Connection-String wird damit für den aktuellen Scope nicht gebraucht.
