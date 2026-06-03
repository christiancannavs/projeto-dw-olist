-- ============================================================
-- 04_analytics.sql
-- Consultas Analíticas de Negócio — 5 queries obrigatórias
-- Dataset: Olist E-Commerce (2016-2018)
-- ============================================================

-- ============================================================
-- QUERY 1: ANÁLISE TEMPORAL — Evolução de vendas por mês
-- Mostra como receita e volume de pedidos evoluíram ao longo do tempo
-- Permite identificar sazonalidade e tendência de crescimento
-- ============================================================
SELECT
    d.year                              AS ano,
    d.month                             AS mes,
    d.month_name                        AS nome_mes,
    COUNT(DISTINCT f.order_id)          AS total_pedidos,
    COUNT(*)                            AS total_itens,
    ROUND(SUM(f.price), 2)              AS receita_produtos,
    ROUND(SUM(f.freight_value), 2)      AS receita_frete,
    ROUND(SUM(f.total_revenue), 2)      AS receita_total,
    ROUND(AVG(f.price), 2)              AS ticket_medio_item,
    ROUND(AVG(f.review_score), 2)       AS avaliacao_media
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- ============================================================
-- QUERY 2: RANKING — Top 10 categorias por receita
-- Identifica quais categorias de produtos são mais lucrativas
-- Apoia decisões de mix de produtos e estoque
-- ============================================================
SELECT
    p.product_category                  AS categoria,
    COUNT(DISTINCT f.order_id)          AS total_pedidos,
    COUNT(*)                            AS itens_vendidos,
    ROUND(SUM(f.price), 2)              AS receita_total,
    ROUND(AVG(f.price), 2)              AS preco_medio,
    ROUND(SUM(f.price) * 100.0 /
          SUM(SUM(f.price)) OVER (), 2) AS pct_receita,
    ROUND(AVG(f.review_score), 2)       AS avaliacao_media
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY p.product_category
ORDER BY receita_total DESC
LIMIT 10;

-- ============================================================
-- QUERY 3: AGREGAÇÃO MULTIDIMENSIONAL — Receita por categoria × estado
-- Cruzamento que responde: qual categoria vende mais em cada estado?
-- Ideal para estratégias regionais de marketing e logística
-- ============================================================
SELECT
    p.product_category                  AS categoria,
    c.customer_state                    AS estado,
    COUNT(DISTINCT f.order_id)          AS total_pedidos,
    ROUND(SUM(f.price), 2)              AS receita_total,
    ROUND(AVG(f.price), 2)              AS ticket_medio,
    ROUND(AVG(f.freight_value), 2)      AS frete_medio,
    ROUND(AVG(f.review_score), 2)       AS avaliacao_media
FROM fact_sales f
JOIN dim_product p  ON f.product_key  = p.product_key
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY p.product_category, c.customer_state
ORDER BY receita_total DESC
LIMIT 50;

-- ============================================================
-- QUERY 4: COHORT / RETENÇÃO — Análise do mês de primeira compra
-- Mostra quando cada "coorte" de clientes entrou na plataforma
-- Mede crescimento da base de clientes mês a mês
-- ============================================================
WITH primeira_compra AS (
    -- Para cada cliente, encontra o mês/ano da primeira compra
    SELECT
        dc.customer_unique_id,
        MIN(d.year * 100 + d.month)         AS cohort_ano_mes,
        MIN(d.full_date)                    AS data_primeira_compra,
        EXTRACT('year' FROM MIN(d.full_date)) AS cohort_ano,
        EXTRACT('month' FROM MIN(d.full_date)) AS cohort_mes
    FROM fact_sales f
    JOIN dim_customer dc ON f.customer_key = dc.customer_key
    JOIN dim_date d       ON f.date_key    = d.date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY dc.customer_unique_id
),
compras_repetidas AS (
    -- Conta quantos clientes fizeram mais de 1 pedido
    SELECT
        dc.customer_unique_id,
        COUNT(DISTINCT f.order_id) AS total_pedidos
    FROM fact_sales f
    JOIN dim_customer dc ON f.customer_key = dc.customer_key
    GROUP BY dc.customer_unique_id
)
SELECT
    pc.cohort_ano                           AS ano,
    pc.cohort_mes                           AS mes,
    COUNT(*)                                AS novos_clientes,
    SUM(COUNT(*)) OVER (
        ORDER BY pc.cohort_ano, pc.cohort_mes
    )                                       AS clientes_acumulados,
    COUNT(CASE WHEN cr.total_pedidos > 1
               THEN 1 END)                  AS clientes_recorrentes,
    ROUND(COUNT(CASE WHEN cr.total_pedidos > 1 THEN 1 END) * 100.0
          / COUNT(*), 2)                    AS pct_retencao
FROM primeira_compra pc
LEFT JOIN compras_repetidas cr
    ON pc.customer_unique_id = cr.customer_unique_id
GROUP BY pc.cohort_ano, pc.cohort_mes
ORDER BY pc.cohort_ano, pc.cohort_mes;

-- ============================================================
-- QUERY 5: KPI — Ticket médio, NPS e prazo por estado
-- Painel de indicadores-chave por estado do cliente
-- Permite comparar performance operacional e satisfação por região
-- ============================================================
SELECT
    c.customer_state                        AS estado,
    COUNT(DISTINCT f.order_id)              AS total_pedidos,
    COUNT(DISTINCT c.customer_unique_id)    AS clientes_unicos,
    ROUND(AVG(f.price), 2)                  AS ticket_medio,
    ROUND(SUM(f.price), 2)                  AS receita_total,
    ROUND(AVG(f.freight_value), 2)          AS frete_medio,
    -- NPS simplificado: % promotores (score 5) - % detratores (score 1-2)
    ROUND(
        (COUNT(CASE WHEN f.review_score = 5 THEN 1 END) * 100.0 /
         NULLIF(COUNT(f.review_score), 0))
        -
        (COUNT(CASE WHEN f.review_score <= 2 THEN 1 END) * 100.0 /
         NULLIF(COUNT(f.review_score), 0))
    , 2)                                    AS nps_estimado,
    ROUND(AVG(f.review_score), 2)           AS avaliacao_media,
    ROUND(AVG(f.days_to_delivery), 1)       AS prazo_medio_entrega_dias,
    ROUND(AVG(f.delivery_delay), 1)         AS atraso_medio_dias,
    -- % de entregas no prazo
    ROUND(
        COUNT(CASE WHEN COALESCE(f.delivery_delay, 0) <= 0 THEN 1 END) * 100.0
        / NULLIF(COUNT(f.days_to_delivery), 0)
    , 2)                                    AS pct_entrega_no_prazo
FROM fact_sales f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY c.customer_state
ORDER BY receita_total DESC;
