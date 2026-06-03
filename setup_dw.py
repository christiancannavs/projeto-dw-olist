"""
setup_dw.py
Cria o banco olist_dw.duckdb e gera os 4 graficos.
Uso: python setup_dw.py
Rode este arquivo de DENTRO da pasta projeto-dw-olist (ou projeto-dw-olis).
"""

import duckdb
import os
import sys

# ── Localiza a pasta data ──────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data").replace("\\", "/")
DB   = os.path.join(BASE, "olist_dw.duckdb")

print(f"Pasta do projeto : {BASE}")
print(f"Pasta de dados   : {DATA}")
print(f"Banco DuckDB     : {DB}")

# Verifica se os CSVs existem
csvs = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "product_category_name_translation.csv",
]
missing = [c for c in csvs if not os.path.exists(os.path.join(BASE, "data", c))]
if missing:
    print(f"\nERRO: CSVs nao encontrados em {DATA}:")
    for m in missing:
        print(f"  - {m}")
    sys.exit(1)

print("\nCSVs encontrados. Iniciando pipeline...\n")

conn = duckdb.connect(DB)

# ── 00 STAGING ────────────────────────────────────────────────────
print("00. Criando views de staging...")
conn.execute(f"""
DROP VIEW IF EXISTS stg_orders;
DROP VIEW IF EXISTS stg_order_items;
DROP VIEW IF EXISTS stg_customers;
DROP VIEW IF EXISTS stg_products;
DROP VIEW IF EXISTS stg_sellers;
DROP VIEW IF EXISTS stg_order_payments;
DROP VIEW IF EXISTS stg_order_reviews;
DROP VIEW IF EXISTS stg_category_translation;

CREATE VIEW stg_orders            AS SELECT * FROM read_csv_auto('{DATA}/olist_orders_dataset.csv', header=true);
CREATE VIEW stg_order_items       AS SELECT * FROM read_csv_auto('{DATA}/olist_order_items_dataset.csv', header=true);
CREATE VIEW stg_customers         AS SELECT * FROM read_csv_auto('{DATA}/olist_customers_dataset.csv', header=true);
CREATE VIEW stg_products          AS SELECT * FROM read_csv_auto('{DATA}/olist_products_dataset.csv', header=true);
CREATE VIEW stg_sellers           AS SELECT * FROM read_csv_auto('{DATA}/olist_sellers_dataset.csv', header=true);
CREATE VIEW stg_order_payments    AS SELECT * FROM read_csv_auto('{DATA}/olist_order_payments_dataset.csv', header=true);
CREATE VIEW stg_order_reviews     AS SELECT * FROM read_csv_auto('{DATA}/olist_order_reviews_dataset.csv', header=true);
CREATE VIEW stg_category_translation AS SELECT * FROM read_csv_auto('{DATA}/product_category_name_translation.csv', header=true);
""")
print("   OK\n")

# ── 01 OLTP ───────────────────────────────────────────────────────
print("01. Normalizando dados (OLTP)...")
conn.execute("""
DROP TABLE IF EXISTS oltp_customers;
DROP TABLE IF EXISTS oltp_products;
DROP TABLE IF EXISTS oltp_sellers;
DROP TABLE IF EXISTS oltp_orders;
DROP TABLE IF EXISTS oltp_order_items;
DROP TABLE IF EXISTS oltp_order_payments;
DROP TABLE IF EXISTS oltp_order_reviews;

CREATE TABLE oltp_customers AS
SELECT DISTINCT
    customer_unique_id,
    UPPER(TRIM(customer_city))   AS customer_city,
    UPPER(TRIM(customer_state))  AS customer_state,
    CAST(customer_zip_code_prefix AS VARCHAR) AS customer_zip_code_prefix
FROM stg_customers
WHERE customer_unique_id IS NOT NULL AND customer_state IS NOT NULL;

CREATE TABLE oltp_products AS
SELECT
    p.product_id,
    COALESCE(t.product_category_name_english, 'uncategorized') AS product_category,
    COALESCE(p.product_name_lenght, 0)        AS product_name_length,
    COALESCE(p.product_description_lenght, 0) AS product_description_length,
    COALESCE(p.product_photos_qty, 0)         AS product_photos_qty,
    COALESCE(p.product_weight_g, 0)           AS product_weight_g,
    COALESCE(p.product_length_cm, 0)          AS product_length_cm,
    COALESCE(p.product_height_cm, 0)          AS product_height_cm,
    COALESCE(p.product_width_cm, 0)           AS product_width_cm
FROM stg_products p
LEFT JOIN stg_category_translation t ON p.product_category_name = t.product_category_name
WHERE p.product_id IS NOT NULL;

CREATE TABLE oltp_sellers AS
SELECT DISTINCT
    seller_id,
    UPPER(TRIM(seller_city))  AS seller_city,
    UPPER(TRIM(seller_state)) AS seller_state,
    CAST(seller_zip_code_prefix AS VARCHAR) AS seller_zip_code_prefix
FROM stg_sellers WHERE seller_id IS NOT NULL;

CREATE TABLE oltp_orders AS
SELECT
    order_id, customer_id, order_status,
    TRY_CAST(order_purchase_timestamp AS TIMESTAMP)      AS order_purchase_timestamp,
    TRY_CAST(order_approved_at AS TIMESTAMP)             AS order_approved_at,
    TRY_CAST(order_delivered_carrier_date AS TIMESTAMP)  AS order_delivered_carrier_date,
    TRY_CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    TRY_CAST(order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date
FROM stg_orders
WHERE order_id IS NOT NULL AND customer_id IS NOT NULL AND order_purchase_timestamp IS NOT NULL;

CREATE TABLE oltp_order_items AS
SELECT order_id, order_item_id, product_id, seller_id,
       TRY_CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
       COALESCE(price, 0) AS price,
       COALESCE(freight_value, 0) AS freight_value
FROM stg_order_items
WHERE order_id IS NOT NULL AND product_id IS NOT NULL AND seller_id IS NOT NULL AND price >= 0;

CREATE TABLE oltp_order_payments AS
SELECT order_id, payment_type,
       SUM(payment_installments) AS payment_installments,
       SUM(payment_value)        AS total_payment_value
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY payment_value DESC) AS rn
    FROM stg_order_payments WHERE order_id IS NOT NULL AND payment_value >= 0
) t WHERE rn = 1
GROUP BY order_id, payment_type;

CREATE TABLE oltp_order_reviews AS
SELECT review_id, order_id, review_score,
       TRY_CAST(review_creation_date AS TIMESTAMP) AS review_creation_date
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_creation_date DESC) AS rn
    FROM stg_order_reviews WHERE order_id IS NOT NULL AND review_score BETWEEN 1 AND 5
) t WHERE rn = 1;
""")
for t in ['oltp_customers','oltp_products','oltp_sellers','oltp_orders','oltp_order_items']:
    n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"   {t}: {n:,} linhas")
print("   OK\n")

# ── 02 DW MODEL ───────────────────────────────────────────────────
print("02. Criando estrutura do DW (dimensoes + fato)...")
conn.execute("""
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_seller;

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY, full_date DATE NOT NULL,
    year INTEGER, quarter INTEGER, month INTEGER, month_name VARCHAR(20),
    week_of_year INTEGER, day_of_month INTEGER, day_of_week INTEGER,
    day_name VARCHAR(20), is_weekend BOOLEAN
);
CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY,
    customer_unique_id VARCHAR(50) NOT NULL,
    customer_city VARCHAR(100), customer_state CHAR(2), customer_zip_code VARCHAR(10),
    scd_start_date DATE NOT NULL, scd_end_date DATE, scd_is_current BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY, product_id VARCHAR(50) NOT NULL,
    product_category VARCHAR(100), product_weight_g INTEGER,
    product_length_cm INTEGER, product_height_cm INTEGER,
    product_width_cm INTEGER, product_volume_cm3 INTEGER
);
CREATE TABLE dim_seller (
    seller_key INTEGER PRIMARY KEY, seller_id VARCHAR(50) NOT NULL,
    seller_city VARCHAR(100), seller_state CHAR(2), seller_zip_code VARCHAR(10)
);
CREATE TABLE fact_sales (
    date_key INTEGER NOT NULL, customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL, seller_key INTEGER NOT NULL,
    order_id VARCHAR(50) NOT NULL, order_item_id INTEGER NOT NULL,
    price DECIMAL(10,2), freight_value DECIMAL(10,2), total_revenue DECIMAL(10,2),
    payment_value DECIMAL(10,2), payment_type VARCHAR(30),
    review_score INTEGER, order_status VARCHAR(20),
    days_to_delivery INTEGER, days_estimated INTEGER, delivery_delay INTEGER,
    PRIMARY KEY (order_id, order_item_id)
);
""")
print("   OK\n")

# ── 03 ETL LOAD ───────────────────────────────────────────────────
print("03. Carregando dados no DW...")

# dim_date
conn.execute("""
INSERT INTO dim_date
SELECT
    CAST(strftime(CAST(range AS DATE), '%Y%m%d') AS INTEGER),
    CAST(range AS DATE),
    EXTRACT('year'    FROM CAST(range AS DATE)),
    EXTRACT('quarter' FROM CAST(range AS DATE)),
    EXTRACT('month'   FROM CAST(range AS DATE)),
    strftime(CAST(range AS DATE), '%B'),
    EXTRACT('week'    FROM CAST(range AS DATE)),
    EXTRACT('day'     FROM CAST(range AS DATE)),
    EXTRACT('dow'     FROM CAST(range AS DATE)) + 1,
    strftime(CAST(range AS DATE), '%A'),
    (EXTRACT('dow'    FROM CAST(range AS DATE)) IN (0, 6))
FROM range(DATE '2016-01-01', DATE '2020-01-01', INTERVAL '1 day');
""")
print(f"   dim_date: {conn.execute('SELECT COUNT(*) FROM dim_date').fetchone()[0]:,} dias")

# dim_customer (SCD2 - 1 row per unique customer, deduplicated)
conn.execute("""
INSERT INTO dim_customer (customer_key, customer_unique_id, customer_city, customer_state,
    customer_zip_code, scd_start_date, scd_end_date, scd_is_current)
SELECT
    ROW_NUMBER() OVER (ORDER BY c.customer_unique_id),
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    c.customer_zip_code_prefix,
    COALESCE(
        (SELECT MIN(TRY_CAST(o.order_purchase_timestamp AS DATE))
         FROM oltp_orders o
         JOIN stg_customers sc2 ON o.customer_id = sc2.customer_id
         WHERE sc2.customer_unique_id = c.customer_unique_id),
        DATE '2016-01-01'
    ),
    NULL,
    TRUE
FROM (
    SELECT customer_unique_id, customer_city, customer_state, customer_zip_code_prefix,
           ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY customer_unique_id) AS rn
    FROM oltp_customers
) c WHERE rn = 1;
""")
print(f"   dim_customer: {conn.execute('SELECT COUNT(*) FROM dim_customer').fetchone()[0]:,} clientes")

# dim_product
conn.execute("""
INSERT INTO dim_product
SELECT ROW_NUMBER() OVER (ORDER BY product_id), product_id, product_category,
    product_weight_g, product_length_cm, product_height_cm, product_width_cm,
    product_length_cm * product_height_cm * product_width_cm
FROM oltp_products;
""")
print(f"   dim_product: {conn.execute('SELECT COUNT(*) FROM dim_product').fetchone()[0]:,} produtos")

# dim_seller
conn.execute("""
INSERT INTO dim_seller
SELECT ROW_NUMBER() OVER (ORDER BY seller_id),
    seller_id, seller_city, seller_state, seller_zip_code_prefix
FROM oltp_sellers;
""")
print(f"   dim_seller: {conn.execute('SELECT COUNT(*) FROM dim_seller').fetchone()[0]:,} vendedores")

# fact_sales
conn.execute("""
INSERT INTO fact_sales
SELECT
    CAST(strftime(TRY_CAST(o.order_purchase_timestamp AS DATE), '%Y%m%d') AS INTEGER),
    dc.customer_key, dp.product_key, ds.seller_key,
    oi.order_id, oi.order_item_id,
    oi.price, oi.freight_value,
    oi.price + oi.freight_value,
    pay.total_payment_value, pay.payment_type,
    rev.review_score, o.order_status,
    CASE WHEN o.order_delivered_customer_date IS NOT NULL
         THEN DATEDIFF('day', TRY_CAST(o.order_purchase_timestamp AS DATE),
                              TRY_CAST(o.order_delivered_customer_date AS DATE)) END,
    DATEDIFF('day', TRY_CAST(o.order_purchase_timestamp AS DATE),
                    TRY_CAST(o.order_estimated_delivery_date AS DATE)),
    CASE WHEN o.order_delivered_customer_date IS NOT NULL AND o.order_estimated_delivery_date IS NOT NULL
         THEN DATEDIFF('day', TRY_CAST(o.order_estimated_delivery_date AS DATE),
                              TRY_CAST(o.order_delivered_customer_date AS DATE)) END
FROM oltp_order_items oi
JOIN oltp_orders o ON oi.order_id = o.order_id
JOIN (
    SELECT customer_id, customer_unique_id,
           ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY customer_id) AS rn
    FROM stg_customers
) sc ON o.customer_id = sc.customer_id AND sc.rn = 1
JOIN dim_customer dc ON sc.customer_unique_id = dc.customer_unique_id AND dc.scd_is_current = TRUE
JOIN dim_product dp ON oi.product_id = dp.product_id
JOIN dim_seller ds ON oi.seller_id = ds.seller_id
LEFT JOIN oltp_order_payments pay ON o.order_id = pay.order_id
LEFT JOIN oltp_order_reviews rev ON o.order_id = rev.order_id
WHERE CAST(strftime(TRY_CAST(o.order_purchase_timestamp AS DATE), '%Y%m%d') AS INTEGER)
      IN (SELECT date_key FROM dim_date);
""")
n_fact = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
print(f"   fact_sales: {n_fact:,} itens")

# Resumo
r = conn.execute("""
SELECT COUNT(DISTINCT order_id), ROUND(SUM(total_revenue),2), ROUND(AVG(review_score),2)
FROM fact_sales WHERE order_status NOT IN ('canceled','unavailable')
""").fetchone()
print(f"\n   Resumo: {r[0]:,} pedidos | R$ {r[1]:,.2f} receita | {r[2]} avaliacao media")
print("   OK\n")

conn.close()

print("=" * 50)
print("Banco criado com sucesso!")
print(f"Arquivo: {DB}")
print("=" * 50)
print("\nAgora rode: python visualizacoes/gerar_graficos.py")
