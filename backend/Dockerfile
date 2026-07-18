# Matches the CI runner (.github/workflows/ci.yml) so the deployed image == the
# tested env. requirements.txt pins numpy==2.4.6 specifically for 3.11 compat
# (2.5.0+ requires >=3.12) — keep this in lockstep with CI's python-version.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# build-essential/libgomp1: scientific wheels (numpy/scipy/statsmodels/sklearn).
# git: requirements.txt installs `sqlguard` from a pinned git tag (our own OSS
# safety guard) — slim images ship no git, so pip would fail without this.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed the SQLite demo at build time so first request is fast (Render free cold-start).
# The data dir is mounted/copied via the repo; skip gracefully if absent.
RUN python -m app.db.seed_demo || echo "seed deferred to runtime"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
