-- ============================================================
-- 00_staging.sql
-- Camada de Staging: lê os CSVs brutos como views temporárias
-- Nenhuma transformação é feita aqui - apenas exposição dos dados
-- ============================================================

-- Remove views existentes para garantir idempotência
DROP VIEW IF EXISTS stg_orders;
DROP VIEW IF EXISTS stg_order_items;
DROP VIEW IF EXISTS stg_customers;
DROP VIEW IF EXISTS stg_products;
DROP VIEW IF EXISTS stg_sellers;
DROP VIEW IF EXISTS stg_order_payments;
DROP VIEW IF EXISTS stg_order_reviews;
DROP VIEW IF EXISTS stg_category_translation;

-- View: pedidos brutos
CREATE VIEW stg_orders AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_orders_dataset.csv', header=true);

-- View: itens dos pedidos (contém preço, frete, produto, vendedor)
CREATE VIEW stg_order_items AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_order_items_dataset.csv', header=true);

-- View: clientes (cidade, estado, CEP)
CREATE VIEW stg_customers AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_customers_dataset.csv', header=true);

-- View: produtos (categoria, dimensões, peso)
CREATE VIEW stg_products AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_products_dataset.csv', header=true);

-- View: vendedores (cidade, estado, CEP)
CREATE VIEW stg_sellers AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_sellers_dataset.csv', header=true);

-- View: pagamentos dos pedidos
CREATE VIEW stg_order_payments AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_order_payments_dataset.csv', header=true);

-- View: avaliações dos pedidos (score 1-5)
CREATE VIEW stg_order_reviews AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/olist_order_reviews_dataset.csv', header=true);

-- View: tradução das categorias (pt → en)
CREATE VIEW stg_category_translation AS
SELECT * FROM read_csv_auto('/home/claude/projeto-dw-olist/data/product_category_name_translation.csv', header=true);

-- Validação rápida do staging
SELECT 'stg_orders' AS tabela, COUNT(*) AS linhas FROM stg_orders
UNION ALL SELECT 'stg_order_items', COUNT(*) FROM stg_order_items
UNION ALL SELECT 'stg_customers', COUNT(*) FROM stg_customers
UNION ALL SELECT 'stg_products', COUNT(*) FROM stg_products
UNION ALL SELECT 'stg_sellers', COUNT(*) FROM stg_sellers
UNION ALL SELECT 'stg_order_payments', COUNT(*) FROM stg_order_payments
UNION ALL SELECT 'stg_order_reviews', COUNT(*) FROM stg_order_reviews
UNION ALL SELECT 'stg_category_translation', COUNT(*) FROM stg_category_translation;
