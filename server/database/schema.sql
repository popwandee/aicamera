-- AI Camera Database Schema
-- Shared between edge (Python) and server (Node.js) components

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
CREATE TYPE camera_status AS ENUM ('active', 'inactive', 'maintenance');
CREATE TYPE detection_status AS ENUM ('pending', 'processed', 'failed');
CREATE TYPE image_quality AS ENUM ('low', 'medium', 'high');

-- Cameras table
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location_lat DECIMAL(10, 8),
    location_lng DECIMAL(11, 8),
    location_address TEXT,
    status camera_status DEFAULT 'active',
    detection_enabled BOOLEAN DEFAULT true,
    image_quality image_quality DEFAULT 'medium',
    upload_interval INTEGER DEFAULT 60,
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Detections table
CREATE TABLE detections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    license_plate VARCHAR(20) NOT NULL,
    confidence DECIMAL(3, 2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    image_url TEXT,
    image_path TEXT,
    location_lat DECIMAL(10, 8),
    location_lng DECIMAL(11, 8),
    vehicle_make VARCHAR(100),
    vehicle_model VARCHAR(100),
    vehicle_color VARCHAR(50),
    vehicle_type VARCHAR(50),
    status detection_status DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    archived BOOLEAN DEFAULT false,
    archived_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analytics table for aggregated data
CREATE TABLE analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_detections INTEGER DEFAULT 0,
    unique_plates INTEGER DEFAULT 0,
    average_confidence DECIMAL(3, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(camera_id, date)
);

-- Camera health monitoring
CREATE TABLE camera_health (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) NOT NULL,
    cpu_usage DECIMAL(5, 2),
    memory_usage DECIMAL(5, 2),
    disk_usage DECIMAL(5, 2),
    temperature DECIMAL(5, 2),
    uptime_seconds BIGINT,
    last_detection_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- System events/logs
CREATE TABLE system_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,
    event_level VARCHAR(20) NOT NULL CHECK (event_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Visualizations table for dashboard charts and graphs
CREATE TABLE visualizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) NOT NULL CHECK (type IN ('chart', 'graph', 'table', 'metric', 'map')),
    configuration JSONB NOT NULL DEFAULT '{}',
    data_source VARCHAR(100) NOT NULL,
    refresh_interval INTEGER DEFAULT 300, -- seconds
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analytics events table for tracking user interactions and system events
CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL CHECK (event_category IN ('user_interaction', 'system_event', 'performance', 'error', 'security')),
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    camera_id UUID REFERENCES cameras(id) ON DELETE SET NULL,
    visualization_id UUID REFERENCES visualizations(id) ON DELETE SET NULL,
    event_data JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_cameras_camera_id ON cameras(camera_id);
CREATE INDEX idx_cameras_status ON cameras(status);
CREATE INDEX idx_detections_camera_id ON detections(camera_id);
CREATE INDEX idx_detections_timestamp ON detections(timestamp);
CREATE INDEX idx_detections_license_plate ON detections(license_plate);
CREATE INDEX idx_detections_status ON detections(status);
CREATE INDEX idx_analytics_camera_date ON analytics(camera_id, date);
CREATE INDEX idx_camera_health_camera_timestamp ON camera_health(camera_id, timestamp);
CREATE INDEX idx_system_events_camera_created ON system_events(camera_id, created_at);
CREATE INDEX idx_system_events_level_created ON system_events(event_level, created_at);
CREATE INDEX idx_visualizations_type ON visualizations(type);
CREATE INDEX idx_visualizations_active ON visualizations(is_active);
CREATE INDEX idx_analytics_events_type_category ON analytics_events(event_type, event_category);
CREATE INDEX idx_analytics_events_created_at ON analytics_events(created_at);
CREATE INDEX idx_analytics_events_user_id ON analytics_events(user_id);
CREATE INDEX idx_analytics_events_camera_id ON analytics_events(camera_id);
CREATE INDEX idx_analytics_events_visualization_id ON analytics_events(visualization_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_cameras_updated_at BEFORE UPDATE ON cameras
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_detections_updated_at BEFORE UPDATE ON detections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_updated_at BEFORE UPDATE ON analytics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visualizations_updated_at BEFORE UPDATE ON visualizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries
CREATE VIEW camera_summary AS
SELECT 
    c.id,
    c.camera_id,
    c.name,
    c.status,
    c.location_lat,
    c.location_lng,
    c.location_address,
    COUNT(d.id) as total_detections,
    COUNT(DISTINCT d.license_plate) as unique_plates,
    AVG(d.confidence) as average_confidence,
    MAX(d.timestamp) as last_detection,
    c.created_at,
    c.updated_at
FROM cameras c
LEFT JOIN detections d ON c.id = d.camera_id
GROUP BY c.id, c.camera_id, c.name, c.status, c.location_lat, c.location_lng, c.location_address, c.created_at, c.updated_at;

-- Create function to update analytics
CREATE OR REPLACE FUNCTION update_daily_analytics()
RETURNS void AS $$
BEGIN
    INSERT INTO analytics (camera_id, date, total_detections, unique_plates, average_confidence)
    SELECT 
        camera_id,
        DATE(timestamp) as date,
        COUNT(*) as total_detections,
        COUNT(DISTINCT license_plate) as unique_plates,
        AVG(confidence) as average_confidence
    FROM detections
    WHERE DATE(timestamp) = CURRENT_DATE
    GROUP BY camera_id, DATE(timestamp)
    ON CONFLICT (camera_id, date) 
    DO UPDATE SET
        total_detections = EXCLUDED.total_detections,
        unique_plates = EXCLUDED.unique_plates,
        average_confidence = EXCLUDED.average_confidence,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Insert sample data for testing
INSERT INTO cameras (camera_id, name, location_lat, location_lng, location_address) VALUES
('cam-001', 'Main Entrance Camera', 30.7128, 100.0060, '123 Main St, Chiangmai, TH'),
('cam-002', 'Side Entrance Camera', 30.7130, 100.0058, '125 Main St, Chiangmai, TH'),
('cam-003', 'Parking Lot Camera', 30.7125, 100.0065, '120 Main St, Chiangmai, TH');

-- Create comments for documentation
COMMENT ON TABLE cameras IS 'Edge camera devices that perform LPR detection';
COMMENT ON TABLE detections IS 'License plate detection results from edge cameras';
COMMENT ON TABLE analytics IS 'Daily aggregated analytics data';
COMMENT ON TABLE camera_health IS 'Camera health monitoring data';
COMMENT ON TABLE system_events IS 'System events and logs';
COMMENT ON TABLE visualizations IS 'Dashboard visualizations and charts configuration';
COMMENT ON TABLE analytics_events IS 'User interactions and system events for analytics';
COMMENT ON VIEW camera_summary IS 'Summary view of cameras with detection statistics';
