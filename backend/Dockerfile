# 3.13 matches the version the pinned requirements are tested against (some pins,
# e.g. numpy 2.5.x, require >=3.12), so the deployed image == the tested env.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# System deps for scientific wheels (numpy/scipy/statsmodels/sklearn).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed the SQLite demo at build time so first request is fast (Render free cold-start).
# The data dir is mounted/copied via the repo; skip gracefully if absent.
RUN python -m app.db.seed_demo || echo "seed deferred to runtime"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
