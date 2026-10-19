# Installing Community Choir Robe Fitting

## Prerequisites

- Python **3.11 or newer** (`python3 --version`)
- `pip` for that interpreter
- SQLite support (bundled with Python's standard library — nothing to install)
- No Node, no Docker, no database server, no internet access at runtime

The project pins its dependency manager: **pip with `requirements.txt`**. There is no
venv requirement — install against the interpreter you will run.

## One-command install

```bash
sh install.sh
```

`install.sh` runs, non-interactively and unprivileged:

1. upgrades `pip`, `setuptools`, `wheel`;
2. installs `requirements.txt` (Django + the pytest test tooling);
3. creates `.env` with a generated `SECRET_KEY` if `.env` does not exist;
4. applies migrations (`python3 manage.py migrate --noinput`);
5. loads demo data (`python3 manage.py seed`);
6. runs `manage.py check` and **exits** — it never starts the server.

## Run it

```bash
python3 manage.py runserver 0.0.0.0:8000
```

Then open <http://127.0.0.1:8000/>. Demo director: `cenius` / `cenius`
(or `cenius@cenius.ai` / `cenius`). Demo singer: `nadia` / `singer-demo`.

`manage.py runserver` also self-heals: on every boot it re-applies pending migrations and
re-runs the idempotent seed, so a fresh clone with no database still lands on a populated
app.

## Manual equivalent (no script)

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
python3 manage.py migrate --noinput
python3 manage.py seed
python3 manage.py runserver 0.0.0.0:8000
```

## Tests

```bash
python3 manage.py test        # Django test runner
python3 -m pytest -q          # same suite through pytest-django
```

Both are offline, need no fixtures on disk and take a couple of seconds.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | generated dev fallback | Django signing key; `install.sh` writes a random one to `.env` |
| `DJANGO_DEBUG` | `true` | Verbose error pages locally |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated host allowlist |
| `DJANGO_CSRF_ORIGINS` | empty | Comma-separated trusted origins behind a proxy |
| `DATABASE_URL` | `sqlite:///./db.sqlite3` | `sqlite:///…`, `postgres://…`, `mysql://…` |
| `PORT` | `8000` | Only if you wrap the run command; runserver takes the port argument above |

`.env` is optional and git-ignored; copy `.env.example` if you want to change anything.

## Deploying for real

- Set a strong `SECRET_KEY` and `DJANGO_DEBUG=false` in the environment.
- Set `DJANGO_ALLOWED_HOSTS` to your hostnames and `DJANGO_CSRF_ORIGINS` to your origins.
- Terminate TLS at the proxy and enable Django's `SECURE_*` settings there.
- Remove or re-password the demo accounts (`cenius`, `nadia`, `rowan`, `aisling`); accounts
  are provisioned by `manage.py seed` and the Django admin, not by a sign-up form.

## Troubleshooting

- **`Address already in use`** — another `runserver` is holding port 8000. Stop it or run
  on another port: `python3 manage.py runserver 0.0.0.0:8001`.
- **Blank page / missing styling** — confirm `/static/css/app.css` returns 200; the app
  runs with `DEBUG=true` so Django serves static files without `collectstatic`.
- **Login bounces back to the sign-in card** — the preview must be served over plain HTTP;
  never enable `SESSION_COOKIE_SECURE` / `SECURE_SSL_REDIRECT` in front of it.
- **Empty screens** — run `python3 manage.py seed`; it is safe to run any time.
