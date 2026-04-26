#!/usr/bin/env bash
# Create aicamera_app database and run schema + grant (requires sudo for postgres).
# Run from repo root or server/database: ./server/database/init-aicamera-app.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating database aicamera_app..."
sudo -u postgres psql -c "CREATE DATABASE aicamera_app OWNER postgres ENCODING 'UTF8';" 2>/dev/null || true

echo "Running schema.sql..."
sudo -u postgres psql -d aicamera_app -f schema.sql

echo "Granting privileges to lpruser..."
sudo -u postgres psql -d aicamera_app -f grant-lpruser.sql

echo "Done. Set DATABASE_URL=postgresql://lpruser:YOUR_PASSWORD@localhost:5432/aicamera_app and start backend-api."
