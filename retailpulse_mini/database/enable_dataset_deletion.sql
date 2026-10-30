-- Run once as root in MySQL Workbench. No data is deleted by this script.
-- Grant deletion only to the application account, never to the chatbot reader.
GRANT DELETE ON retailpulse_mini.dataset_rows TO 'retailpulse_app'@'127.0.0.1';
GRANT DELETE ON retailpulse_mini.datasets TO 'retailpulse_app'@'127.0.0.1';
