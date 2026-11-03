#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copy the local SQLite data (drugs, users, promo codes, redemptions) into Postgres.

Usage:
    DATABASE_URL="postgresql://user:pass@host/db" \
        python3 backend/scripts/migrate_to_postgres.py \
        --source backend/public/drugs_database.db

The script is idempotent for drugs/users/promos: existing emails/codes are skipped.
Use --dry-run to see what would be copied without writing anything.
"""

import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Neo Drug SQLite data to Postgres")
    parser.add_argument(
        "--source",
        default=os.path.join(ROOT_DIR, "backend", "public", "drugs_database.db"),
        help="Path to the source SQLite database",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()

    source_path = os.path.abspath(args.source)
    if not os.path.exists(source_path):
        print(f"Source database not found: {source_path}")
        return 1

    target_url = (os.getenv("DATABASE_URL") or "").strip()
    if not target_url:
        print("DATABASE_URL is not set. Refusing to guess the target database.")
        return 1

    # Point the application's own engine at the source SQLite file before importing
    # models, then create a separate engine for the Postgres target.
    os.environ["DATABASE_URL"] = f"sqlite:///{source_path}"
    os.environ.pop("VERCEL", None)
    os.environ.pop("AWS_LAMBDA_FUNCTION_NAME", None)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app import models
    from backend.app.database import _normalize_database_url

    source_engine = create_engine(f"sqlite:///{source_path}", future=True)
    SourceSession = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)

    if args.dry_run:
        with SourceSession() as src:
            print(f"Drugs:        {src.query(models.Drug).count()}")
            print(f"Users:        {src.query(models.User).count()}")
            print(f"Promo codes:  {src.query(models.PromoCode).count()}")
            print(f"Redemptions:  {src.query(models.PromoRedemption).count()}")
        return 0

    target_engine = create_engine(
        _normalize_database_url(target_url),
        pool_pre_ping=True,
        future=True,
    )
    models.Base.metadata.create_all(bind=target_engine)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)

    def columns_without_id(model):
        return [column.name for column in model.__table__.columns if column.name != "id"]

    with SourceSession() as src, TargetSession() as dst:
        # --- Drugs ---------------------------------------------------------
        existing_drugs = dst.query(models.Drug).count()
        if existing_drugs:
            print(f"Target already has {existing_drugs} drugs — skipping drugs.")
        else:
            drug_columns = columns_without_id(models.Drug)
            copied = 0
            for drug in src.query(models.Drug).yield_per(1000):
                dst.add(models.Drug(**{name: getattr(drug, name) for name in drug_columns}))
                copied += 1
                if copied % 1000 == 0:
                    dst.commit()
                    print(f"  drugs: {copied}")
            dst.commit()
            print(f"Copied {copied} drugs.")

        # --- Users ---------------------------------------------------------
        user_columns = columns_without_id(models.User)
        email_to_id = {}
        copied_users = 0
        for user in src.query(models.User).all():
            existing = dst.query(models.User).filter(models.User.email == user.email).first()
            if existing:
                email_to_id[user.email] = existing.id
                continue
            new_user = models.User(**{name: getattr(user, name) for name in user_columns})
            dst.add(new_user)
            dst.flush()
            email_to_id[user.email] = new_user.id
            copied_users += 1
        dst.commit()
        print(f"Copied {copied_users} users.")

        # --- Promo codes ---------------------------------------------------
        code_to_id = {}
        copied_promos = 0
        for promo in src.query(models.PromoCode).all():
            existing = dst.query(models.PromoCode).filter(models.PromoCode.code == promo.code).first()
            if existing:
                code_to_id[promo.code] = existing.id
                continue
            new_promo = models.PromoCode(
                code=promo.code,
                tier_granted=promo.tier_granted,
                duration_days=promo.duration_days,
                max_uses=promo.max_uses,
                used_count=promo.used_count,
                is_active=promo.is_active,
                expires_at=promo.expires_at,
                created_at=promo.created_at,
            )
            dst.add(new_promo)
            dst.flush()
            code_to_id[promo.code] = new_promo.id
            copied_promos += 1
        dst.commit()
        print(f"Copied {copied_promos} promo codes.")

        # --- Redemptions ---------------------------------------------------
        copied_redemptions = 0
        for redemption in src.query(models.PromoRedemption).all():
            user = src.query(models.User).filter(models.User.id == redemption.user_id).first()
            promo = src.query(models.PromoCode).filter(models.PromoCode.id == redemption.promo_code_id).first()
            if not user or not promo:
                continue
            new_user_id = email_to_id.get(user.email)
            new_promo_id = code_to_id.get(promo.code)
            if not new_user_id or not new_promo_id:
                continue
            exists = dst.query(models.PromoRedemption).filter(
                models.PromoRedemption.user_id == new_user_id,
                models.PromoRedemption.promo_code_id == new_promo_id,
            ).first()
            if exists:
                continue
            dst.add(models.PromoRedemption(
                user_id=new_user_id,
                promo_code_id=new_promo_id,
                code_used=redemption.code_used,
                redeemed_at=redemption.redeemed_at,
            ))
            copied_redemptions += 1
        dst.commit()
        print(f"Copied {copied_redemptions} redemptions.")

    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
