-- ============================================================
-- 03_etl_load.sql
-- Carga ETL: popula dim_date, dimensões e fact_sales
-- Idempotente: DELETE + INSERT a cada execução
-- ============================================================

-- ============================================================
-- PASSO 1: Carregar dim_date
-- Gera 1 linha por dia entre 2016-01-01 e 2019-12-31
-- Cobre todo o período dos dados Olist (2016-2018 + margem)
-- ============================================================
DELETE FROM dim_date;

INSERT INTO dim_date (
    date_key, full_date, year, quarter, month, month_name,
    week_of_year, day_of_month, day_of_week, day_name, is_weekend
)
SELECT
    CAST(strftime(gs.dt, '%Y%m%d') AS INTEGER)          AS date_key,
    gs.dt                                                AS full_date,
    EXTRACT('year'  FROM gs.dt)                         AS year,
    EXTRACT('quarter' FROM gs.dt)                       AS quarter,
    EXTRACT('month' FROM gs.dt)                         AS month,
    strftime(gs.dt, '%B')                               AS month_name,
    EXTRACT('week'  FROM gs.dt)                         AS week_of_year,
    EXTRACT('day'   FROM gs.dt)                         AS day_of_month,
    EXTRACT('dow'   FROM gs.dt) + 1                     AS day_of_week,
    strftime(gs.dt, '%A')                               AS day_name,
    (EXTRACT('dow' FROM gs.dt) IN (0, 6))               AS is_weekend
FROM (
    SELECT CAST(range AS DATE) AS dt
    FROM range(DATE '2016-01-01', DATE '2020-01-01', INTERVAL '1 day')
) gs;

-- ============================================================
-- PASSO 2: Carregar dim_customer (SCD Type 2)
-- Cada customer_unique_id recebe 1 registro "current"
-- scd_start_date = data do primeiro pedido do cliente
-- (SCD2 simulado: em produção, haveria UPDATE quando cidade muda)
-- ============================================================
DELETE FROM dim_customer;

INSERT INTO dim_customer (
    customer_key, customer_unique_id, customer_city, customer_state,
    customer_zip_code, scd_start_date, scd_end_date, scd_is_current
)
SELECT
    ROW_NUMBER() OVER (ORDER BY c.customer_unique_id) AS customer_key,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    c.customer_zip_code_prefix,
    -- scd_start_date = data do primeiro pedido do cliente
    COALESCE(
        MIN(TRY_CAST(o.order_purchase_timestamp AS DATE))
            OVER (PARTITION BY c.customer_unique_id),
        DATE '2016-01-01'
    )                                                  AS scd_start_date,
    NULL                                               AS scd_end_date,     -- registro atual
    TRUE                                               AS scd_is_current
FROM oltp_customers c
LEFT JOIN (
    -- mapeia customer_id → customer_unique_id via orders
    SELECT DISTINCT oc.customer_id, sc.customer_unique_id,
           oc.order_purchase_timestamp
    FROM oltp_orders oc
    JOIN stg_customers sc ON oc.customer_id = sc.customer_id
) o ON c.customer_unique_id = o.customer_unique_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id ORDER BY c.customer_unique_id) = 1;

-- ============================================================
-- PASSO 3: Carregar dim_product
-- ============================================================
DELETE FROM dim_product;

INSERT INTO dim_product (
    product_key, product_id, product_category,
    product_weight_g, product_length_cm, product_height_cm, product_width_cm,
    product_volume_cm3
)
SELECT
    ROW_NUMBER() OVER (ORDER BY product_id) AS product_key,
    product_id,
    product_category,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_length_cm * product_height_cm * product_width_cm AS product_volume_cm3
FROM oltp_products;

-- ============================================================
-- PASSO 4: Carregar dim_seller
-- ============================================================
DELETE FROM dim_seller;

INSERT INTO dim_seller (
    seller_key, seller_id, seller_city, seller_state, seller_zip_code
)
SELECT
    ROW_NUMBER() OVER (ORDER BY seller_id) AS seller_key,
    seller_id,
    seller_city,
    seller_state,
    seller_zip_code_prefix
FROM oltp_sellers;

-- ============================================================
-- PASSO 5: Carregar fact_sales
-- Join central: orders → order_items → customers → products → sellers
-- Adiciona métricas de pagamento, avaliação e prazo de entrega
-- ============================================================
DELETE FROM fact_sales;

INSERT INTO fact_sales (
    date_key, customer_key, product_key, seller_key,
    order_id, order_item_id,
    price, freight_value, total_revenue,
    payment_value, payment_type,
    review_score, order_status,
    days_to_delivery, days_estimated, delivery_delay
)
SELECT
    -- date_key: baseado na data de compra
    CAST(strftime(TRY_CAST(o.order_purchase_timestamp AS DATE), '%Y%m%d') AS INTEGER) AS date_key,

    -- customer_key: via customer_unique_id (SCD2 – versão atual)
    dc.customer_key,

    -- product_key
    dp.product_key,

    -- seller_key
    ds.seller_key,

    -- identificadores do item
    oi.order_id,
    oi.order_item_id,

    -- métricas de valor
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value                         AS total_revenue,

    -- pagamento (pode ser NULL se pedido não foi pago ainda)
    pay.total_payment_value                             AS payment_value,
    pay.payment_type,

    -- avaliação (NULL se o cliente não avaliou)
    rev.review_score,

    -- status
    o.order_status,

    -- métricas de tempo (em dias)
    CASE WHEN o.order_delivered_customer_date IS NOT NULL
         THEN DATEDIFF('day',
                TRY_CAST(o.order_purchase_timestamp AS DATE),
                TRY_CAST(o.order_delivered_customer_date AS DATE))
    END AS days_to_delivery,

    DATEDIFF('day',
        TRY_CAST(o.order_purchase_timestamp AS DATE),
        TRY_CAST(o.order_estimated_delivery_date AS DATE)
    )   AS days_estimated,

    CASE WHEN o.order_delivered_customer_date IS NOT NULL
              AND o.order_estimated_delivery_date IS NOT NULL
         THEN DATEDIFF('day',
                TRY_CAST(o.order_estimated_delivery_date AS DATE),
                TRY_CAST(o.order_delivered_customer_date AS DATE))
    END AS delivery_delay

FROM oltp_order_items oi

-- Join com pedidos
JOIN oltp_orders o
    ON oi.order_id = o.order_id

-- Join com clientes (via stg_customers para obter customer_unique_id)
JOIN stg_customers sc
    ON o.customer_id = sc.customer_id
JOIN dim_customer dc
    ON sc.customer_unique_id = dc.customer_unique_id
    AND dc.scd_is_current = TRUE

-- Join com produtos
JOIN dim_product dp
    ON oi.product_id = dp.product_id

-- Join com vendedores
JOIN dim_seller ds
    ON oi.seller_id = ds.seller_id

-- Join com pagamentos (LEFT: nem todo pedido tem pagamento registrado)
LEFT JOIN oltp_order_payments pay
    ON o.order_id = pay.order_id

-- Join com avaliações (LEFT: cliente pode não ter avaliado)
LEFT JOIN oltp_order_reviews rev
    ON o.order_id = rev.order_id

-- Garante que a data existe na dim_date
WHERE CAST(strftime(TRY_CAST(o.order_purchase_timestamp AS DATE), '%Y%m%d') AS INTEGER)
      IN (SELECT date_key FROM dim_date);

-- ============================================================
-- VALIDAÇÕES PÓS-CARGA
-- ============================================================
SELECT '== CONTAGEM DW ==' AS info;
SELECT 'dim_date'     AS tabela, COUNT(*) AS linhas FROM dim_date
UNION ALL SELECT 'dim_customer', COUNT(*) FROM dim_customer
UNION ALL SELECT 'dim_product',  COUNT(*) FROM dim_product
UNION ALL SELECT 'dim_seller',   COUNT(*) FROM dim_seller
UNION ALL SELECT 'fact_sales',   COUNT(*) FROM fact_sales;

-- Checa NULLs nas chaves estrangeiras da fato
SELECT '== CHECAGEM DE INTEGRIDADE ==' AS info;
SELECT 'fact sem date_key válido'    AS check_name,
       COUNT(*) AS qtd
FROM fact_sales f
WHERE NOT EXISTS (SELECT 1 FROM dim_date d WHERE d.date_key = f.date_key)
UNION ALL
SELECT 'fact sem customer_key válido', COUNT(*)
FROM fact_sales f
WHERE NOT EXISTS (SELECT 1 FROM dim_customer c WHERE c.customer_key = f.customer_key)
UNION ALL
SELECT 'fact sem product_key válido', COUNT(*)
FROM fact_sales f
WHERE NOT EXISTS (SELECT 1 FROM dim_product p WHERE p.product_key = f.product_key)
UNION ALL
SELECT 'fact sem seller_key válido', COUNT(*)
FROM fact_sales f
WHERE NOT EXISTS (SELECT 1 FROM dim_seller s WHERE s.seller_key = f.seller_key);

-- Resumo de receita total carregada
SELECT '== RESUMO FINANCEIRO ==' AS info;
SELECT
    COUNT(DISTINCT order_id)    AS total_pedidos,
    COUNT(*)                    AS total_itens,
    ROUND(SUM(price), 2)        AS receita_produtos,
    ROUND(SUM(freight_value),2) AS receita_frete,
    ROUND(SUM(total_revenue),2) AS receita_total,
    ROUND(AVG(review_score),2)  AS avaliacao_media
FROM fact_sales;
