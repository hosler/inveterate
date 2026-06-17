FROM python:3.13-slim

# Build deps for psycopg (Postgres C driver)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the files needed for the editable install (`-e .[all]`) first so the
# dependency layer caches independently of later source changes.
COPY requirements.txt pyproject.toml README.md LICENSE.txt ./
COPY inveterate ./inveterate
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home app \
    && mkdir -p /app/logs \
    && chown -R app /app
USER app

CMD ["gunicorn", "-k", "gevent", "-b", "0.0.0.0:8000", "--workers", "4", "config.wsgi:application"]
