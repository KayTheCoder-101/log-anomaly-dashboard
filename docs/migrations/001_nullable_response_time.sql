-- Makes response_time_ms nullable to support real-world log sources
-- (e.g. NASA HTTP logs) that don't report it.
ALTER TABLE logs ALTER COLUMN response_time_ms DROP NOT NULL;
