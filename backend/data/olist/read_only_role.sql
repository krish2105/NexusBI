-- Read-only role pattern for Nexus BI target-database execution.
-- Review and adapt the role name for your environment.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='nexus_readonly') THEN
    CREATE ROLE nexus_readonly NOLOGIN;
  END IF;
END $$;
DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO nexus_readonly', current_database()); END $$;
GRANT USAGE ON SCHEMA nexus_demo TO nexus_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA nexus_demo TO nexus_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA nexus_demo GRANT SELECT ON TABLES TO nexus_readonly;
ALTER ROLE nexus_readonly SET default_transaction_read_only = on;
ALTER ROLE nexus_readonly SET statement_timeout = '8s';
