-- Run once as your MySQL administrator in Workbench.
-- Additive migration: original retail tables and their data are untouched.
USE retailpulse_mini;
CREATE TABLE IF NOT EXISTS datasets (
  dataset_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(180) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  import_hash CHAR(64) NOT NULL UNIQUE,
  columns_json JSON NOT NULL,
  row_count INT UNSIGNED NOT NULL,
  rejected_count INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS dataset_rows (
  row_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  dataset_id BIGINT UNSIGNED NOT NULL,
  payload JSON NOT NULL,
  FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id),
  INDEX idx_dataset_rows_dataset (dataset_id)
) ENGINE=InnoDB;
-- The existing app account's SELECT, INSERT grants on retailpulse_mini.*
-- already cover these two new tables.
GRANT SELECT ON retailpulse_mini.dataset_rows TO 'retailpulse_reader'@'127.0.0.1';
-- Dataset deletion is a user-confirmed application action; the reader remains SELECT-only.
GRANT DELETE ON retailpulse_mini.dataset_rows TO 'retailpulse_app'@'127.0.0.1';
GRANT DELETE ON retailpulse_mini.datasets TO 'retailpulse_app'@'127.0.0.1';
