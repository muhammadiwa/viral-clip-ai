-- Development Database Initialization
-- This script sets up basic database extensions and initial data

-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create development user if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'viralclip_dev') THEN
        CREATE ROLE viralclip_dev WITH LOGIN PASSWORD 'dev_password_123';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE viralclip_dev TO viralclip;
GRANT ALL PRIVILEGES ON DATABASE viralclip_dev TO viralclip_dev;

-- Create uploads directory table for tracking
CREATE TABLE IF NOT EXISTS uploads_temp (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert development notice
INSERT INTO uploads_temp (filename) VALUES ('Development environment initialized') ON CONFLICT DO NOTHING;