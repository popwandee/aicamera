-- Optional: add archived support for detections (soft delete / archive)
-- Run with: psql -U postgres -d aicamera_app -f add_detections_archived.sql
ALTER TABLE detections ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT false;
ALTER TABLE detections ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;
