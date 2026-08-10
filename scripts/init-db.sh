#!/bin/bash
set -euo pipefail

docker compose -f biblioteca-compose.yml -p biblioteca-migracao up -d

echo "Waiting for PostgreSQL to start..."
until docker compose -f biblioteca-compose.yml -p biblioteca-migracao exec postgres pg_isready -U postgres; do
  sleep 2
done

echo "Creating odoo role..."
docker compose -f biblioteca-compose.yml -p biblioteca-migracao exec postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -c \
  "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'odoo') THEN CREATE ROLE odoo WITH LOGIN CREATEDB PASSWORD 'odoo'; END IF; END \$\$;"

echo "Restoring databases..."
docker compose -f biblioteca-compose.yml -p biblioteca-migracao exec postgres \
  pg_restore --exit-on-error -U postgres -d biblioteca /dumps/20260715_0304_dados.dump
docker compose -f biblioteca-compose.yml -p biblioteca-migracao exec postgres \
  pg_restore --exit-on-error -U postgres -d biblioteca /dumps/20260715_0309_arquivos.dump

echo "Initialization and restoration complete!"
