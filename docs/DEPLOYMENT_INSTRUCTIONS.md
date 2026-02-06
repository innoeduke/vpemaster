# Fresh Docker Deployment Instructions

This guide explains how to perform a fresh deployment of the VPEMaster app.

## 1. Prerequisites
The database metadata is managed via Flask-Migrate. The initial baseline migration includes the necessary data seeding.

## 2. Deploying with Docker
Build and start your containers:

```bash
docker-compose up -d --build
```

## 3. Initialize the Database
Once the containers are running, simply run the database migrations. This will create the schema and seed the initial metadata.

```bash
docker-compose exec web flask db upgrade
```

## 4. Verification
After the upgrade, the database will contain:
- Populated metadata tables (`roles`, `pathways`, etc.)
- Empty user/transaction tables (`Users`, `Contacts`, `Meetings`, `Session_Logs`, etc.)

You can now proceed with creating your initial admin user or other setup steps.

## Troubleshooting: Version Mismatch
If you receive an error like `Can't locate revision identified by '...'` on an existing server, run this one-liner to reset the migration record:

```bash
python3 -c "from app import create_app, db; import sqlalchemy as sa; app=create_app(); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('DROP TABLE IF EXISTS alembic_version')); db.session.commit()"
```

Then run the setup again:
```bash
flask db stamp head
python scripts/seed_metadata.py
flask db upgrade
```

> [!NOTE]
> `flask db upgrade` only runs the seeding logic on a **fresh** database. If you have an existing database and use `stamp head`, you must run `python scripts/seed_metadata.py` manually to populate the metadata.
