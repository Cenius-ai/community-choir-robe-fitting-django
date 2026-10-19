#!/usr/bin/env bash
# Install project dependencies and prepare the database. Never starts the server.
set -euo pipefail
cd "$(dirname "$0")"

export CI=true
export PIP_DISABLE_PIP_VERSION_CHECK=1

echo "==> Upgrading pip, setuptools and wheel"
python3 -m pip install --upgrade --quiet pip setuptools wheel

echo "==> Installing Python dependencies from requirements.txt"
if ! python3 -m pip install --quiet -r requirements.txt; then
  # The runtime dependency is what matters; the pytest tooling is only needed
  # to run the test suite, so an offline install of it must not block boot.
  echo "WARNING: could not install all of requirements.txt (offline?)." >&2
  echo "         Falling back to the runtime dependency only." >&2
  python3 -m pip install --quiet "Django==5.2.16"
fi

if [ ! -f .env ]; then
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  printf 'SECRET_KEY=%s\n' "$secret" > .env
  echo "==> Wrote .env with a freshly generated SECRET_KEY"
fi

echo "==> Applying database migrations"
python3 manage.py migrate --noinput

echo "==> Loading idempotent demo data"
python3 manage.py seed

echo "==> Checking the Django project"
python3 manage.py check

cat <<'EOF'

Setup complete.

Start the app with:
  python3 manage.py runserver 0.0.0.0:8000

Sign in at http://127.0.0.1:8000/accounts/login/
  Director : cenius / cenius           (also cenius@cenius.ai / cenius)
  Singer   : nadia / singer-demo
EOF
