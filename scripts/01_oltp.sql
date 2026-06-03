-- ============================================================
-- 01_oltp.sql
-- Camada OLTP: normalização, deduplicação e limpeza dos dados
-- Transforma os dados brutos do staging em tabelas relacionais
-- ============================================================

-- Remove tabelas para idempotência
DROP TABLE IF EXISTS oltp_customers;
DROP TABLE IF EXISTS oltp_products;
DROP TABLE IF EXISTS oltp_sellers;
DROP TABLE IF EXISTS oltp_orders;
DROP TABLE IF EXISTS oltp_order_items;
DROP TABLE IF EXISTS oltp_order_payments;
DROP TABLE IF EXISTS oltp_order_reviews;

-- --------------------------------------------------------
-- oltp_customers: clientes únicos com dados limpos
-- Usa customer_unique_id para deduplicar (mesmo cliente, vários pedidos)
-- --------------------------------------------------------
CREATE TABLE oltp_customers AS
SELECT DISTINCT
    customer_unique_id,
    -- Capitaliza nome da cidade
    initcap(TRIM(customer_city))    AS customer_city,
    UPPER(TRIM(customer_state))     AS customer_state,
    CAST(customer_zip_code_prefix AS VARCHAR) AS customer_zip_code_prefix
FROM stg_customers
WHERE customer_unique_id IS NOT NULL
  AND customer_state IS NOT NULL;

-- --------------------------------------------------------
-- oltp_products: produtos com categoria traduzida para inglês
-- --------------------------------------------------------
CREATE TABLE oltp_products AS
SELECT
    p.product_id,
    COALESCE(t.product_category_name_english, 'uncategorized') AS product_category,
    COALESCE(p.product_name_lenght, 0)          AS product_name_length,
    COALESCE(p.product_description_lenght, 0)   AS product_description_length,
    COALESCE(p.product_photos_qty, 0)           AS product_photos_qty,
    COALESCE(p.product_weight_g, 0)             AS product_weight_g,
    COALESCE(p.product_length_cm, 0)            AS product_length_cm,
    COALESCE(p.product_height_cm, 0)            AS product_height_cm,
    COALESCE(p.product_width_cm, 0)             AS product_width_cm
FROM stg_products p
LEFT JOIN stg_category_translation t
    ON p.product_category_name = t.product_category_name
WHERE p.product_id IS NOT NULL;

-- --------------------------------------------------------
-- oltp_sellers: vendedores únicos com dados limpos
-- --------------------------------------------------------
CREATE TABLE oltp_sellers AS
SELECT DISTINCT
    seller_id,
    initcap(TRIM(seller_city))   AS seller_city,
    UPPER(TRIM(seller_state))    AS seller_state,
    CAST(seller_zip_code_prefix AS VARCHAR) AS seller_zip_code_prefix
FROM stg_sellers
WHERE seller_id IS NOT NULL;

-- --------------------------------------------------------
-- oltp_orders: pedidos com status e timestamps limpos
-- Filtra apenas pedidos com status válidos e datas não nulas
-- --------------------------------------------------------
CREATE TABLE oltp_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    TRY_CAST(order_purchase_timestamp AS TIMESTAMP)       AS order_purchase_timestamp,
    TRY_CAST(order_approved_at AS TIMESTAMP)              AS order_approved_at,
    TRY_CAST(order_delivered_carrier_date AS TIMESTAMP)   AS order_delivered_carrier_date,
    TRY_CAST(order_delivered_customer_date AS TIMESTAMP)  AS order_delivered_customer_date,
    TRY_CAST(order_estimated_delivery_date AS TIMESTAMP)  AS order_estimated_delivery_date
FROM stg_orders
WHERE order_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND order_purchase_timestamp IS NOT NULL
  AND order_status IN ('delivered', 'shipped', 'invoiced', 'processing', 'approved', 'canceled', 'unavailable', 'created');

-- --------------------------------------------------------
-- oltp_order_items: itens dos pedidos com valores positivos
-- --------------------------------------------------------
CREATE TABLE oltp_order_items AS
SELECT
    order_id,
    order_item_id,
    product_id,
    seller_id,
    TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
    COALESCE(price, 0)          AS price,
    COALESCE(freight_value, 0)  AS freight_value
FROM stg_order_items
WHERE order_id IS NOT NULL
  AND product_id IS NOT NULL
  AND seller_id IS NOT NULL
  AND price >= 0;

-- --------------------------------------------------------
-- oltp_order_payments: consolidado por pedido
-- Agrega múltiplos pagamentos (ex: cartão + vale) em 1 linha
-- --------------------------------------------------------
CREATE TABLE oltp_order_payments AS
SELECT
    order_id,
    -- Tipo de pagamento principal (maior valor)
    payment_type,
    SUM(payment_installments) AS payment_installments,
    SUM(payment_value)        AS total_payment_value
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY payment_value DESC) AS rn
    FROM stg_order_payments
    WHERE order_id IS NOT NULL
      AND payment_value >= 0
)
WHERE rn = 1
GROUP BY order_id, payment_type;

-- --------------------------------------------------------
-- oltp_order_reviews: uma avaliação por pedido (mais recente)
-- --------------------------------------------------------
CREATE TABLE oltp_order_reviews AS
SELECT DISTINCT ON (order_id)
    review_id,
    order_id,
    review_score,
    TRY_CAST(review_creation_date AS TIMESTAMP) AS review_creation_date
FROM stg_order_reviews
WHERE order_id IS NOT NULL
  AND review_score BETWEEN 1 AND 5
ORDER BY order_id, review_creation_date DESC;

-- --------------------------------------------------------
-- Validação OLTP
-- --------------------------------------------------------
SELECT 'oltp_customers' AS tabela, COUNT(*) AS linhas FROM oltp_customers
UNION ALL SELECT 'oltp_products', COUNT(*) FROM oltp_products
UNION ALL SELECT 'oltp_sellers', COUNT(*) FROM oltp_sellers
UNION ALL SELECT 'oltp_orders', COUNT(*) FROM oltp_orders
UNION ALL SELECT 'oltp_order_items', COUNT(*) FROM oltp_order_items
UNION ALL SELECT 'oltp_order_payments', COUNT(*) FROM oltp_order_payments
UNION ALL SELECT 'oltp_order_reviews', COUNT(*) FROM oltp_order_reviews;
