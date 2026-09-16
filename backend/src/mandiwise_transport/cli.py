"""Local administrator utilities; farmer self-registration lives in the portal."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import jwt
from sqlalchemy import select

from .db import Location, User, database


def issue_token(user_id, secret, hours=1):
    if len(secret.encode()) < 32:
        raise ValueError("JWT_SECRET must contain at least 32 bytes")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "iat": now,
            "exp": now + timedelta(hours=hours),
            "iss": "mandiwise",
            "aud": "mandiwise-transport",
        },
        secret,
        algorithm="HS256",
    )


def seed_markets(db, data_dir):
    """Only current-feed exact identities. Never guess cross-source aliases/coordinates."""
    locations = {}
    for path in sorted(Path(data_dir).glob("punjab_*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            key = (row["state"], row["district"], row["market"])
            locations.setdefault(key, path.name)
    added = 0
    for (state, district, name), source in sorted(locations.items()):
        exists = db.scalar(
            select(Location).where(
                Location.state == state,
                Location.district == district,
                Location.name == name,
                Location.kind == "mandi",
            )
        )
        if not exists:
            key = json.dumps([state, district, name], ensure_ascii=False)
            db.add(
                Location(
                    id=str(uuid5(NAMESPACE_URL, "mandiwise:datagov:" + key)),
                    state=state,
                    district=district,
                    name=name,
                    kind="mandi",
                    source=f"data.gov.in snapshot: data/{source}",
                )
            )
            added += 1
    db.commit()
    return {
        "added": added,
        "distinct_source_markets": len(locations),
        "note": "No coordinates, distances, or rates inferred. CEDA aliases not merged.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("create-user")
    add.add_argument("--name", required=True)
    add.add_argument("--role", choices=["farmer", "coordinator", "admin"], required=True)
    token = sub.add_parser("token")
    token.add_argument("user_id")
    token.add_argument("--hours", type=int, choices=range(1, 25), default=1)
    seed = sub.add_parser("seed-markets")
    seed.add_argument("--data-dir", default="../data")
    args = parser.parse_args()
    engine, sessions = database()
    try:
        with sessions() as db:
            if args.command == "create-user":
                if not 1 <= len(args.name.strip()) <= 160:
                    parser.error("Name must contain 1..160 characters")
                user = User(name=args.name.strip(), role=args.role)
                db.add(user)
                db.commit()
                print(json.dumps({"id": user.id, "name": user.name, "role": user.role}))
            elif args.command == "token":
                user = db.get(User, args.user_id)
                if user is None or not user.active:
                    parser.error("Unknown or inactive user")
                print(issue_token(user.id, os.getenv("JWT_SECRET", ""), args.hours))
            else:
                print(json.dumps(seed_markets(db, args.data_dir)))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
