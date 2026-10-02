import sys

from app.db import SessionLocal
from app.services import auth as auth_service


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m app.scripts.make_admin <username>", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        try:
            user = auth_service.make_admin(db, argv[0])
        except auth_service.UserNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
    print(f"{user.username} is now admin")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
