-- WHY: This initialization script creates additional databases for n8n.
-- It runs automatically when the PostgreSQL container is first started.

-- Create n8n database
-- WHY: n8n requires its own database to store workflows, credentials, and execution history.
-- Separating n8n data from application data improves maintainability and allows
-- independent backups and scaling.
CREATE DATABASE n8n;

-- Grant permissions
-- WHY: The postgres user needs full access to manage both databases
GRANT ALL PRIVILEGES ON DATABASE n8n TO postgres;

-- Create test database
-- WHY: Testing requires an isolated database to prevent test data from
-- affecting development or production data.
CREATE DATABASE automation_platform_test;
GRANT ALL PRIVILEGES ON DATABASE automation_platform_test TO postgres;
