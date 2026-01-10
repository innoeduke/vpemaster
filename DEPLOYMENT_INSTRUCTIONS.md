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
