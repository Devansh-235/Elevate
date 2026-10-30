-- Run once in MySQL Workbench with an administrator. MySQL 8.0.16+ required.
CREATE DATABASE IF NOT EXISTS retailpulse_mini
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
USE retailpulse_mini;

CREATE TABLE IF NOT EXISTS customers (
  customer_id VARCHAR(64) PRIMARY KEY,
  customer_name VARCHAR(160) NOT NULL,
  CHECK (CHAR_LENGTH(TRIM(customer_name)) > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR(64) PRIMARY KEY,
  product_name VARCHAR(160) NOT NULL,
  category VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uploaded_files (
  upload_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  file_name VARCHAR(255) NOT NULL,
  file_hash CHAR(64) NOT NULL UNIQUE,
  total_records INT UNSIGNED NOT NULL,
  valid_records INT UNSIGNED NOT NULL,
  invalid_records INT UNSIGNED NOT NULL,
  inserted_records INT UNSIGNED NOT NULL,
  uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CHECK (total_records = valid_records + invalid_records),
  CHECK (inserted_records <= valid_records)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  order_id VARCHAR(64) PRIMARY KEY,
  order_date DATE NOT NULL,
  customer_id VARCHAR(64) NOT NULL,
  city VARCHAR(100) NOT NULL,
  region VARCHAR(100) NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
  INDEX idx_orders_date (order_date),
  INDEX idx_orders_location (region, city)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  order_id VARCHAR(64) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(12,2) NOT NULL,
  cost_price DECIMAL(12,2) NOT NULL,
  discount DECIMAL(6,5) NOT NULL DEFAULT 0,
  revenue DECIMAL(25,7) GENERATED ALWAYS AS
    (quantity * unit_price * (1 - discount)) STORED,
  profit DECIMAL(25,7) GENERATED ALWAYS AS
    (quantity * unit_price * (1 - discount) - quantity * cost_price) STORED,
  upload_id BIGINT UNSIGNED NOT NULL,
  UNIQUE KEY uq_order_product (order_id, product_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (upload_id) REFERENCES uploaded_files(upload_id),
  CHECK (quantity > 0 AND quantity <= 1000000),
  CHECK (unit_price >= 0 AND cost_price >= 0),
  CHECK (discount >= 0 AND discount <= 1)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_history (
  chat_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id CHAR(36) NOT NULL,
  question TEXT NOT NULL,
  generated_sql TEXT NOT NULL,
  query_parameters JSON NOT NULL,
  answer TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_chat_session (session_id, created_at)
) ENGINE=InnoDB;

-- One denormalized, read-only analytics surface. Names and upload/chat logs excluded.
CREATE OR REPLACE SQL SECURITY DEFINER VIEW retail_sales AS
SELECT oi.order_item_id, o.order_id, o.order_date, o.customer_id,
       p.product_id, p.product_name, p.category, oi.quantity,
       oi.unit_price, oi.cost_price, oi.discount, o.city, o.region,
       oi.revenue, oi.profit
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id;

-- Account provisioning: replace BOTH passwords before running these lines.
-- Run the CREATE/GRANT statements below separately in Workbench.
-- CREATE USER 'retailpulse_app'@'127.0.0.1' IDENTIFIED BY 'YOUR_STRONG_APP_PASSWORD';
-- GRANT SELECT, INSERT ON retailpulse_mini.* TO 'retailpulse_app'@'127.0.0.1';
-- GRANT UPDATE ON retailpulse_mini.customers TO 'retailpulse_app'@'127.0.0.1';
-- GRANT UPDATE ON retailpulse_mini.products TO 'retailpulse_app'@'127.0.0.1';
-- GRANT UPDATE ON retailpulse_mini.orders TO 'retailpulse_app'@'127.0.0.1';
-- CREATE USER 'retailpulse_reader'@'127.0.0.1' IDENTIFIED BY 'YOUR_STRONG_READER_PASSWORD';
-- GRANT SELECT ON retailpulse_mini.retail_sales TO 'retailpulse_reader'@'127.0.0.1';
