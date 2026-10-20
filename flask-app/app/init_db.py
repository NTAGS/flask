import os
import subprocess
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import DB, create_app, seed_products

app = create_app()

MAX_ATTEMPTS = int(os.getenv("DB_INIT_MAX_ATTEMPTS", "30"))
RETRY_SECONDS = int(os.getenv("DB_INIT_RETRY_SECONDS", "2"))

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        with app.app_context():
            DB.session.execute(text("SELECT 1"))
        break
    except OperationalError as exc:
        if attempt == MAX_ATTEMPTS:
            raise
        print(f"database not ready (attempt {attempt}/{MAX_ATTEMPTS}); retrying: {exc}")
        time.sleep(RETRY_SECONDS)

subprocess.run(
    [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"],
    check=True,
)

with app.app_context():
    seed_products()

print("database migrations and seed data ready")
