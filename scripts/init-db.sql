-- GPW Trading Advisor Database Initialization Script

-- Set timezone
SET timezone = 'Europe/Warsaw';

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create database user if not exists (may need to be done by superuser)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolename = 'gpw_user') THEN

      CREATE ROLE gpw_user LOGIN PASSWORD 'gpw_password';
   END IF;
END
$do$;

-- Grant necessary privileges
GRANT ALL PRIVILEGES ON DATABASE gpw_advisor_db TO gpw_user;
GRANT ALL ON SCHEMA public TO gpw_user;

-- Create indexes for better performance (these will be created by Django migrations too)
-- But we can prepare the database for optimal performance

-- Ensure UTF8 encoding
ALTER DATABASE gpw_advisor_db SET client_encoding TO 'utf8';
ALTER DATABASE gpw_advisor_db SET default_transaction_isolation TO 'read committed';
ALTER DATABASE gpw_advisor_db SET timezone TO 'Europe/Warsaw';

-- Log the initialization
\echo 'GPW Trading Advisor database initialized successfully'
