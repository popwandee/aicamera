-- Grant privileges to lpruser for aicamera_app (run as superuser after schema.sql)
-- Usage: sudo -u postgres psql -d aicamera_app -f grant-lpruser.sql

GRANT USAGE ON SCHEMA public TO lpruser;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO lpruser;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO lpruser;

GRANT SELECT ON camera_summary TO lpruser;

GRANT EXECUTE ON FUNCTION update_updated_at_column() TO lpruser;
GRANT EXECUTE ON FUNCTION update_daily_analytics() TO lpruser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lpruser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO lpruser;
