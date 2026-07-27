#!/bin/bash

docker compose -p biblioteca-migracao up -d

echo "Waiting for PostgreSQL to start..."
until docker compose -p biblioteca-migracao exec postgres pg_isready -U postgres; do
  sleep 2
done

echo "Creating odoo role..."
docker compose -p biblioteca-migracao exec postgres psql -U postgres -c "CREATE ROLE odoo WITH LOGIN CREATEDB PASSWORD 'odoo';"

echo "Restoring databases..."
docker compose -p biblioteca-migracao exec postgres pg_restore -U postgres -d biblioteca /dumps/20260715_0304_dados.dump
docker compose -p biblioteca-migracao exec postgres pg_restore -U postgres -d biblioteca /dumps/20260715_0309_arquivos.dump

echo "Initialization and restoration complete!"
