-- Database initialization script
-- This script runs when PostgreSQL container starts for the first time

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance
-- These will be created by Prisma migrations, but keeping here for reference

-- Create a dedicated user for the application (if not using Docker defaults)
-- CREATE USER aicamera WITH PASSWORD 'aicamera123';
-- GRANT ALL PRIVILEGES ON DATABASE aicamera TO aicamera;