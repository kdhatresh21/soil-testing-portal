CREATE DATABASE IF NOT EXISTS soil_testing_portal_public
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE soil_testing_portal_public;

-- The Flask-SQLAlchemy command `flask --app app create-db` creates the tables.
-- This file intentionally creates the database only; table definitions are maintained in app.py.