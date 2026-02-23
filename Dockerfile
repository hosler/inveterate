FROM python:3.13-slim

# Build deps for psycopg (Postgres C driver)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home app
USER app

CMD ["gunicorn", "-k", "gevent", "-b", "0.0.0.0:8000", "--workers", "4", "config.wsgi:application"]
