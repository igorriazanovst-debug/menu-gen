"""
Дамп базы PostgreSQL из Docker и коммит в git.
Запускать из корня проекта:
  python db_dump_and_commit.py
  python db_dump_and_commit.py --message "my commit message"
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).parent
ENV = dotenv_values(ROOT / ".env")

DB_NAME = ENV.get("DB_NAME")
DB_USER = ENV.get("DB_USER")

DUMP_DIR = ROOT / "backups" / "db"
DUMP_FILE = DUMP_DIR / "dump.sql"


def run(cmd: list[str], **kwargs):
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"ERROR: {' '.join(cmd)}")
        sys.exit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", "-m", default=None)
    args = parser.parse_args()

    if not DB_NAME or not DB_USER:
        print("ERROR: DB_NAME или DB_USER не найдены в .env")
        sys.exit(1)

    DUMP_DIR.mkdir(parents=True, exist_ok=True)

    # Добавляем backups/db/ в .gitignore исключение (если нужно)
    gitignore = ROOT / ".gitignore"
    gitignore_text = gitignore.read_text(encoding="utf-8")
    if "backups/db/" not in gitignore_text:
        # Убеждаемся что backups/db не заигнорен
        pass  # по умолчанию не в .gitignore

    print(f"Дамп базы {DB_NAME}...")
    run([
        "docker", "compose", "exec", "-T", "db",
        "pg_dump",
        "-U", DB_USER,
        "-d", DB_NAME,
        "--no-owner",
        "--no-acl",
    ], stdout=open(DUMP_FILE, "w", encoding="utf-8"))

    print(f"Дамп сохранён: {DUMP_FILE}")

    # git add + commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    message = args.message or f"db dump {timestamp}"

    run(["git", "add", str(DUMP_FILE)], cwd=ROOT)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=ROOT
    )
    if result.returncode == 0:
        print("Нет изменений для коммита (дамп не изменился)")
        return

    run(["git", "commit", "-m", message], cwd=ROOT)
    print(f"Закоммичено: {message}")


if __name__ == "__main__":
    main()
