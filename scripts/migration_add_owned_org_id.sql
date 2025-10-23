-- Migration: Add owned_org_id to users table
-- Purpose: Support 1 user = 1 owned organization model
-- Date: 2025-10-22

-- Add owned_org_id column to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS owned_org_id UUID;

-- Add foreign key constraint
ALTER TABLE users 
ADD CONSTRAINT fk_users_owned_org 
FOREIGN KEY (owned_org_id) 
REFERENCES organizations(id) 
ON DELETE CASCADE;

-- Add unique constraint (one organization per owner)
ALTER TABLE users 
ADD CONSTRAINT uq_users_owned_org 
UNIQUE (owned_org_id);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_users_owned_org_id 
ON users(owned_org_id);

-- Comments
COMMENT ON COLUMN users.owned_org_id IS 'Organization ID that this user owns (null for team members)';

-- Verification queries
-- SELECT * FROM users WHERE owned_org_id IS NOT NULL; -- List all owners
-- SELECT * FROM users WHERE owned_org_id IS NULL; -- List all team members
