"""CLI for administrative tasks.

Usage:
    uv run python -m src.cli reset-password <name>
"""

import argparse
import getpass
import sys

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.domain.auth import validate_password_strength
from src.domain.exceptions import ValidationError
from src.infrastructure.auth.password import hash_password
from src.infrastructure.persistence.models.person_model import PersonModel


def _reset_password(name: str) -> None:
    settings = get_settings()
    sync_url = settings.database.url.replace("+aiosqlite", "")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        stmt = select(PersonModel).where(func.lower(PersonModel.name) == name.lower())
        person = session.execute(stmt).scalars().first()
        if person is None:
            print(f"No person found with name '{name}'")
            sys.exit(1)

        password = getpass.getpass(f"New password for {person.name}: ")
        try:
            validate_password_strength(password)
        except ValidationError as e:
            print(f"Error: {e}")
            sys.exit(1)

        person.password_hash = hash_password(password)
        session.commit()
        print(f"Password reset for {person.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Couplefins CLI")
    sub = parser.add_subparsers(dest="command")
    reset = sub.add_parser("reset-password", help="Reset a person's password")
    reset.add_argument("name", help="Person name")
    args = parser.parse_args()

    command: str = args.command
    if command == "reset-password":
        name: str = args.name
        _reset_password(name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
