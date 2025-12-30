# Fresh Docker Deployment Instructions

This guide explains how to perform a fresh deployment of the VPEMaster app with the required metadata migration.

## 1. Prerequisites
The `scripts/` directory now contains two new artifacts:
- `export_metadata.py`: Used to snapshot the current metadata.
- `metadata_dump.json`: The snapshot of the 6 metadata tables (`level_roles`, `pathways`, `pathway_projects`, `projects`, `roles`, `session_types`).
- `seed_metadata.py`: Used to initialize the new database with this snapshot.

A generated `metadata_dump.json` is already present. If you need to update it from your current environment, run:
```bash
python3 scripts/export_metadata.py
```

## 2. Deploying with Docker
Build and start your containers as usual:

```bash
docker-compose up -d --build
```

## 3. Initialize the Database
Once the containers are running, you need to run the seed script inside the `web` container. This will:
1. **DROP ALL TABLES** (Zeroing strictly all other tables).
2. Re-create the database schema.
3. Import the data from `metadata_dump.json` into the 6 metadata tables.

Run the following command:

```bash
docker-compose exec web python scripts/seed_metadata.py
```

## 4. Verification
After seeding, the database will contain:
- Populated metadata tables (`roles`, `pathways`, etc.)
- Empty user/transaction tables (`users`, `contacts`, `meetings`, `session_logs`, etc.)

You can now proceed with creating your initial admin user or other setup steps.
