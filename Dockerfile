FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DEBUG must be False here so collectstatic uses the same whitenoise
# manifest storage backend the container serves with at runtime (settings.py
# switches storage backends based on DEBUG). SECRET_KEY/DATABASE_URL aren't
# needed at build time — collectstatic doesn't touch the database and falls
# back to the insecure dev SECRET_KEY placeholder, which is fine unused.
RUN DEBUG=False python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
