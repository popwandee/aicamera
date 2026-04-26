-- Seed sample data for UI development and testing
-- Run AFTER schema.sql (and grant-lpruser.sql). Requires cameras to exist (from schema or previous insert).
-- Usage: sudo -u postgres psql -d aicamera_app -f /home/devuser/aicamera/server/database/seed-sample-data.sql

-- Ensure we have at least one camera (if schema did not insert any)
INSERT INTO cameras (camera_id, name, location_lat, location_lng, location_address)
SELECT 'cam-001', 'Main Entrance Camera', 30.7128, 100.0060, '123 Main St, Chiangmai, TH'
WHERE NOT EXISTS (SELECT 1 FROM cameras WHERE camera_id = 'cam-001');
INSERT INTO cameras (camera_id, name, location_lat, location_lng, location_address)
SELECT 'cam-002', 'Side Entrance Camera', 30.7130, 100.0058, '125 Main St, Chiangmai, TH'
WHERE NOT EXISTS (SELECT 1 FROM cameras WHERE camera_id = 'cam-002');
INSERT INTO cameras (camera_id, name, location_lat, location_lng, location_address)
SELECT 'cam-003', 'Parking Lot Camera', 30.7125, 100.0065, '120 Main St, Chiangmai, TH'
WHERE NOT EXISTS (SELECT 1 FROM cameras WHERE camera_id = 'cam-003');

-- Detections (sample LPR results; camera_id from existing cameras)
INSERT INTO detections (camera_id, timestamp, license_plate, confidence, status, metadata)
SELECT c.id, NOW() - INTERVAL '1 hour', 'กก 1234', 0.92, 'processed', '{"source": "seed"}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1;
INSERT INTO detections (camera_id, timestamp, license_plate, confidence, status, metadata)
SELECT c.id, NOW() - INTERVAL '2 hours', 'ขข 5678', 0.88, 'pending', '{}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1;
INSERT INTO detections (camera_id, timestamp, license_plate, confidence, status, metadata)
SELECT c.id, NOW() - INTERVAL '30 minutes', '1กค 9999', 0.95, 'processed', '{}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-002' LIMIT 1;

-- Analytics (daily aggregates per camera)
INSERT INTO analytics (camera_id, date, total_detections, unique_plates, average_confidence)
SELECT c.id, CURRENT_DATE, 42, 28, 0.89
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1
ON CONFLICT (camera_id, date) DO UPDATE SET total_detections = 42, unique_plates = 28, average_confidence = 0.89;
INSERT INTO analytics (camera_id, date, total_detections, unique_plates, average_confidence)
SELECT c.id, CURRENT_DATE - 1, 35, 22, 0.87
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1
ON CONFLICT (camera_id, date) DO NOTHING;
INSERT INTO analytics (camera_id, date, total_detections, unique_plates, average_confidence)
SELECT c.id, CURRENT_DATE, 18, 15, 0.91
FROM cameras c WHERE c.camera_id = 'cam-002' LIMIT 1
ON CONFLICT (camera_id, date) DO NOTHING;

-- Camera health
INSERT INTO camera_health (camera_id, timestamp, status, cpu_usage, memory_usage, disk_usage, uptime_seconds, metadata)
SELECT c.id, NOW(), 'healthy', 25.5, 42.0, 65.0, 86400, '{"fps": 15}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1;
INSERT INTO camera_health (camera_id, timestamp, status, cpu_usage, memory_usage, metadata)
SELECT c.id, NOW() - INTERVAL '5 minutes', 'healthy', 30.0, 38.0, '{}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-002' LIMIT 1;
INSERT INTO camera_health (camera_id, timestamp, status, metadata)
SELECT c.id, NOW() - INTERVAL '1 hour', 'degraded', '{"reason": "high temp"}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-003' LIMIT 1;

-- System events
INSERT INTO system_events (camera_id, event_type, event_level, message, metadata)
SELECT c.id, 'camera_started', 'info', 'Camera stream started', '{}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1;
INSERT INTO system_events (camera_id, event_type, event_level, message, metadata)
SELECT NULL, 'system_boot', 'info', 'Server started', '{"version": "1.0"}'::jsonb
WHERE NOT EXISTS (SELECT 1 FROM system_events WHERE event_type = 'system_boot' AND message = 'Server started' LIMIT 1);
INSERT INTO system_events (camera_id, event_type, event_level, message, metadata)
SELECT c.id, 'detection_threshold', 'warning', 'Low confidence detection', '{"confidence": 0.65}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-002' LIMIT 1;

-- Visualizations (dashboard widgets config)
INSERT INTO visualizations (name, description, type, configuration, data_source, refresh_interval, is_active, created_by)
VALUES
  ('Detections by Hour', 'Hourly detection count', 'chart', '{"type": "line"}'::jsonb, 'detections', 300, true, 'admin'),
  ('Camera Status', 'Active cameras', 'metric', '{}'::jsonb, 'cameras', 60, true, 'admin'),
  ('Top Plates', 'Most seen plates', 'table', '{"columns": ["license_plate", "count"]}'::jsonb, 'detections', 600, true, NULL),
  ('Map View', 'Camera locations', 'map', '{"zoom": 12}'::jsonb, 'cameras', 300, true, 'admin');

-- Analytics events (user/system tracking)
INSERT INTO analytics_events (event_type, event_category, user_id, event_data)
VALUES ('page_view', 'user_interaction', 'user-1', '{"page": "/server/"}'::jsonb);
INSERT INTO analytics_events (event_type, event_category, camera_id, event_data)
SELECT 'camera_view', 'user_interaction', c.id, '{"tab": "detections"}'::jsonb
FROM cameras c WHERE c.camera_id = 'cam-001' LIMIT 1;
INSERT INTO analytics_events (event_type, event_category, event_data)
VALUES ('api_latency', 'performance', '{"path": "/detections", "ms": 45}'::jsonb);
