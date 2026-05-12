-- Read-only monitoring user consumed by mysqld_exporter.
-- Runs only on first volume init via /docker-entrypoint-initdb.d.
-- For existing volumes, apply this manually:
--   docker exec -i ilovepawn-zugzwang-db-1 mysql -uroot -proot < db/init/01-exporter.sql

CREATE USER IF NOT EXISTS 'exporter'@'%'
  IDENTIFIED BY 'exporter'
  WITH MAX_USER_CONNECTIONS 3;

GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%';

FLUSH PRIVILEGES;
