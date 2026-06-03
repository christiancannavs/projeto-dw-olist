-- ============================================================
-- 02_dw_model.sql
-- Camada Data Warehouse: criação da estrutura dimensional
-- Esquema Estrela com SCD Type 2 em dim_customer
-- ============================================================

-- Remove tabelas em ordem inversa (fato antes das dimensões)
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_seller;

-- ============================================================
-- DIMENSÃO: dim_date
-- Grain: 1 linha por dia do calendário
-- ============================================================
CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,   -- YYYYMMDD como chave surrogate
    full_date       DATE NOT NULL,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,      -- 1-4
    month           INTEGER NOT NULL,      -- 1-12
    month_name      VARCHAR(20) NOT NULL,  -- 'January', etc.
    week_of_year    INTEGER NOT NULL,      -- 1-53
    day_of_month    INTEGER NOT NULL,      -- 1-31
    day_of_week     INTEGER NOT NULL,      -- 1=Sunday...7=Saturday
    day_name        VARCHAR(20) NOT NULL,  -- 'Monday', etc.
    is_weekend      BOOLEAN NOT NULL,
    is_holiday      BOOLEAN DEFAULT FALSE  -- placeholder para feriados
);

-- ============================================================
-- DIMENSÃO: dim_customer (SCD Type 2)
-- Grain: 1 linha por versão de cliente (detecta mudança de cidade/estado)
-- SCD2: rastreia mudanças históricas de localização do cliente
-- ============================================================
CREATE TABLE dim_customer (
    customer_key        INTEGER PRIMARY KEY,    -- surrogate key (auto-increment)
    customer_unique_id  VARCHAR(50) NOT NULL,   -- ID natural (pode ter várias linhas)
    customer_city       VARCHAR(100),
    customer_state      CHAR(2),
    customer_zip_code   VARCHAR(10),
    -- Campos SCD Type 2
    scd_start_date      DATE NOT NULL,
    scd_end_date        DATE,                   -- NULL = registro atual
    scd_is_current      BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- DIMENSÃO: dim_product
-- Grain: 1 linha por produto (SCD Type 1 - sobrescreve)
-- ============================================================
CREATE TABLE dim_product (
    product_key             INTEGER PRIMARY KEY,   -- surrogate key
    product_id              VARCHAR(50) NOT NULL,  -- ID natural
    product_category        VARCHAR(100),
    product_weight_g        INTEGER,
    product_length_cm       INTEGER,
    product_height_cm       INTEGER,
    product_width_cm        INTEGER,
    product_volume_cm3      INTEGER                -- calculado: L*H*W
);

-- ============================================================
-- DIMENSÃO: dim_seller
-- Grain: 1 linha por vendedor
-- ============================================================
CREATE TABLE dim_seller (
    seller_key      INTEGER PRIMARY KEY,    -- surrogate key
    seller_id       VARCHAR(50) NOT NULL,   -- ID natural
    seller_city     VARCHAR(100),
    seller_state    CHAR(2),
    seller_zip_code VARCHAR(10)
);

-- ============================================================
-- TABELA FATO: fact_sales
-- Grain: 1 linha por item de pedido (order_item_id)
-- Métricas: receita (price), frete, avaliação, prazo de entrega
-- ============================================================
CREATE TABLE fact_sales (
    -- Chaves substitutas (foreign keys para dimensões)
    date_key            INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key        INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key         INTEGER NOT NULL REFERENCES dim_product(product_key),
    seller_key          INTEGER NOT NULL REFERENCES dim_seller(seller_key),

    -- Chaves de negócio (para rastreabilidade)
    order_id            VARCHAR(50) NOT NULL,
    order_item_id       INTEGER NOT NULL,

    -- Métricas (fatos)
    price               DECIMAL(10,2) NOT NULL,     -- preço do produto
    freight_value       DECIMAL(10,2) NOT NULL,     -- valor do frete
    total_revenue       DECIMAL(10,2) NOT NULL,     -- price + freight
    payment_value       DECIMAL(10,2),              -- valor total pago
    payment_type        VARCHAR(30),                -- forma de pagamento
    review_score        INTEGER,                    -- avaliação 1-5 (pode ser NULL)
    order_status        VARCHAR(20),

    -- Métricas derivadas de tempo (em dias)
    days_to_delivery    INTEGER,                    -- compra → entrega real
    days_estimated      INTEGER,                    -- compra → entrega estimada
    delivery_delay      INTEGER,                    -- atraso (negativo = adiantado)

    PRIMARY KEY (order_id, order_item_id)
);

-- Confirma criação das tabelas
SELECT table_name, 
       (SELECT COUNT(*) FROM information_schema.columns 
        WHERE table_name = t.table_name) AS num_colunas
FROM information_schema.tables t
WHERE table_schema = 'main'
  AND table_name IN ('dim_date','dim_customer','dim_product','dim_seller','fact_sales')
ORDER BY table_name;
