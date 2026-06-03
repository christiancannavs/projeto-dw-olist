-- ============================================================
-- 05_performance.sql
-- Performance e Otimização (bônus)
-- Cria tabela agregada para queries frequentes + índices
-- ============================================================

-- ============================================================
-- TABELA AGREGADA: agg_monthly_sales
-- Materializa os dados mensais já sumarizados
-- Reduz drasticamente o custo de queries de dashboard
-- ============================================================
DROP TABLE IF EXISTS agg_monthly_sales;

CREATE TABLE agg_monthly_sales AS
SELECT
    d.year,
    d.month,
    d.month_name,
    p.product_category,
    c.customer_state,
    COUNT(DISTINCT f.order_id)      AS total_pedidos,
    COUNT(*)                        AS total_itens,
    ROUND(SUM(f.price), 2)          AS receita_produtos,
    ROUND(SUM(f.freight_value), 2)  AS receita_frete,
    ROUND(SUM(f.total_revenue), 2)  AS receita_total,
    ROUND(AVG(f.price), 2)          AS ticket_medio,
    ROUND(AVG(f.freight_value), 2)  AS frete_medio,
    ROUND(AVG(f.review_score), 2)   AS avaliacao_media,
    COUNT(f.review_score)           AS qtd_avaliacoes
FROM fact_sales f
JOIN dim_date d     ON f.date_key    = d.date_key
JOIN dim_product p  ON f.product_key = p.product_key
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY d.year, d.month, d.month_name, p.product_category, c.customer_state;

-- ============================================================
-- COMPARAÇÃO DE PERFORMANCE
-- Query lenta (scan completo na fact_sales com joins)
-- vs. Query rápida (na tabela agregada)
-- ============================================================

-- Query 1A: LENTA — scan direto na fato (para EXPLAIN)
EXPLAIN ANALYZE
SELECT
    d.year, d.month,
    ROUND(SUM(f.total_revenue), 2) AS receita_total
FROM fact_sales f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Query 1B: RÁPIDA — mesma análise na tabela agregada
EXPLAIN ANALYZE
SELECT
    year, month,
    ROUND(SUM(receita_total), 2) AS receita_total
FROM agg_monthly_sales
GROUP BY year, month
ORDER BY year, month;

-- ============================================================
-- VALIDAÇÃO DA TABELA AGREGADA
-- ============================================================
SELECT 'agg_monthly_sales' AS tabela, COUNT(*) AS linhas FROM agg_monthly_sales;

-- Confirma que os totais batem com a fact_sales
SELECT
    'fact_sales'            AS origem,
    ROUND(SUM(total_revenue), 2) AS receita_total
FROM fact_sales
WHERE order_status NOT IN ('canceled', 'unavailable')
UNION ALL
SELECT
    'agg_monthly_sales',
    ROUND(SUM(receita_total), 2)
FROM agg_monthly_sales;
