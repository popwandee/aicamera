-- Add ip_address column to cameras table
-- Run with: psql -U lpruser -d aicamera_app -f add_cameras_ip_address.sql
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
