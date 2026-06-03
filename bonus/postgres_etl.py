"""
bonus/postgres_etl.py
Bonus: carrega o DW no PostgreSQL e compara performance com DuckDB.
Pre-requisitos:
  pip install psycopg2-binary duckdb pandas tabulate
  PostgreSQL rodando localmente (ou ajuste CONN_STR)

Uso:
  python bonus/postgres_etl.py
"""
import os, sys, time
import duckdb
import pandas as pd

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import execute_values
except ImportError:
    print("ERRO: instale psycopg2-binary\n  pip install psycopg2-binary")
    sys.exit(1)

# ── Configuracao PostgreSQL ───────────────────────────────────────
# Ajuste conforme seu ambiente:
CONN_STR = os.getenv("PG_CONN", "host=localhost dbname=olist_dw user=postgres password=postgres port=5432")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DUCK = os.path.join(BASE, "olist_dw.duckdb")

print("=" * 60)
print("  BONUS: PostgreSQL ETL + Comparacao de Performance")
print("=" * 60)

# ── Conecta DuckDB ────────────────────────────────────────────────
if not os.path.exists(DB_DUCK):
    print(f"ERRO: Banco DuckDB nao encontrado em {DB_DUCK}")
    print("Execute setup_dw.py primeiro.")
    sys.exit(1)

duck = duckdb.connect(DB_DUCK, read_only=True)

# ── Conecta PostgreSQL ────────────────────────────────────────────
try:
    pg = psycopg2.connect(CONN_STR)
    pg.autocommit = False
    cur = pg.cursor()
    print(f"\nPostgreSQL: conectado!")
    cur.execute("SELECT version()")
    print(f"  {cur.fetchone()[0][:60]}")
except Exception as e:
    print(f"\nERRO ao conectar PostgreSQL: {e}")
    print("\nPara testar localmente, instale o PostgreSQL e ajuste CONN_STR.")
    print("Ou defina a variavel de ambiente: PG_CONN='host=... dbname=...'")
    sys.exit(1)

# ── DDL PostgreSQL ────────────────────────────────────────────────
print("\n[1] Criando estrutura no PostgreSQL...")

cur.execute("""
DROP TABLE IF EXISTS fact_sales CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_seller CASCADE;

CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,
    full_date     DATE NOT NULL,
    year          INTEGER, quarter INTEGER, month INTEGER,
    month_name    VARCHAR(20), week_of_year INTEGER,
    day_of_month  INTEGER, day_of_week INTEGER,
    day_name      VARCHAR(20), is_weekend BOOLEAN
);
CREATE TABLE dim_customer (
    customer_key       SERIAL PRIMARY KEY,
    customer_unique_id VARCHAR(50) NOT NULL,
    customer_city      VARCHAR(100), customer_state CHAR(2),
    customer_zip_code  VARCHAR(10),
    scd_start_date     DATE NOT NULL,
    scd_end_date       DATE,
    scd_is_current     BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE dim_product (
    product_key      SERIAL PRIMARY KEY,
    product_id       VARCHAR(50) NOT NULL,
    product_category VARCHAR(100),
    product_weight_g INTEGER, product_length_cm INTEGER,
    product_height_cm INTEGER, product_width_cm INTEGER,
    product_volume_cm3 INTEGER
);
CREATE TABLE dim_seller (
    seller_key   SERIAL PRIMARY KEY,
    seller_id    VARCHAR(50) NOT NULL,
    seller_city  VARCHAR(100), seller_state CHAR(2),
    seller_zip_code VARCHAR(10)
);
CREATE TABLE fact_sales (
    date_key      INTEGER NOT NULL REFERENCES dim_date(date_key),
    customer_key  INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key   INTEGER NOT NULL REFERENCES dim_product(product_key),
    seller_key    INTEGER NOT NULL REFERENCES dim_seller(seller_key),
    order_id      VARCHAR(50) NOT NULL,
    order_item_id INTEGER NOT NULL,
    price         NUMERIC(10,2), freight_value NUMERIC(10,2),
    total_revenue NUMERIC(10,2), payment_value NUMERIC(10,2),
    payment_type  VARCHAR(30), review_score INTEGER,
    order_status  VARCHAR(20), days_to_delivery INTEGER,
    days_estimated INTEGER, delivery_delay INTEGER,
    PRIMARY KEY (order_id, order_item_id)
);
""")
pg.commit()
print("   DDL criado.")

# ── Carga via Pandas ──────────────────────────────────────────────
def load_table(table_name, df, pg_conn):
    cur2 = pg_conn.cursor()
    cols = list(df.columns)
    vals = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]
    query = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES %s ON CONFLICT DO NOTHING"
    execute_values(cur2, query, vals, page_size=1000)
    pg_conn.commit()
    cur2.close()

print("\n[2] Carregando dimensoes no PostgreSQL...")
t0 = time.time()

df_date = duck.execute("SELECT * FROM dim_date").df()
load_table("dim_date", df_date, pg)
print(f"   dim_date:     {len(df_date):,} linhas")

df_cust = duck.execute("SELECT customer_key, customer_unique_id, customer_city, customer_state, customer_zip_code, scd_start_date, scd_end_date, scd_is_current FROM dim_customer").df()
load_table("dim_customer", df_cust, pg)
print(f"   dim_customer: {len(df_cust):,} linhas")

df_prod = duck.execute("SELECT * FROM dim_product").df()
load_table("dim_product", df_prod, pg)
print(f"   dim_product:  {len(df_prod):,} linhas")

df_sell = duck.execute("SELECT * FROM dim_seller").df()
load_table("dim_seller", df_sell, pg)
print(f"   dim_seller:   {len(df_sell):,} linhas")

df_fact = duck.execute("SELECT * FROM fact_sales").df()
load_table("fact_sales", df_fact, pg)
print(f"   fact_sales:   {len(df_fact):,} linhas")

t_load = time.time() - t0
print(f"\n   Carga total: {t_load:.1f}s")

# ── Indices PostgreSQL ────────────────────────────────────────────
print("\n[3] Criando indices no PostgreSQL...")
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_product  ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_status   ON fact_sales(order_status);
ANALYZE fact_sales;
""")
pg.commit()
print("   Indices criados e ANALYZE executado.")

# ── Comparacao de Performance ─────────────────────────────────────
print("\n[4] Comparacao de performance: DuckDB vs PostgreSQL")
print("-" * 60)

QUERY = """
    SELECT
        EXTRACT(YEAR FROM d.full_date) AS ano,
        EXTRACT(MONTH FROM d.full_date) AS mes,
        COUNT(DISTINCT f.order_id) AS pedidos,
        ROUND(SUM(f.price)::numeric, 2) AS receita,
        ROUND(AVG(f.review_score)::numeric, 2) AS avaliacao
    FROM fact_sales f
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY 1, 2
    ORDER BY 1, 2
"""

QUERY_DUCK = """
    SELECT d.year AS ano, d.month AS mes,
        COUNT(DISTINCT f.order_id) AS pedidos,
        ROUND(SUM(f.price), 2) AS receita,
        ROUND(AVG(f.review_score), 2) AS avaliacao
    FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status NOT IN ('canceled','unavailable')
    GROUP BY d.year, d.month ORDER BY d.year, d.month
"""

benchmarks = []

# DuckDB
runs_duck = []
for i in range(3):
    t0 = time.time()
    duck.execute(QUERY_DUCK).df()
    runs_duck.append((time.time() - t0) * 1000)
avg_duck = sum(runs_duck) / len(runs_duck)
benchmarks.append(("DuckDB 1.5.3", f"{avg_duck:.1f} ms", "OLAP nativo, colunar"))

# PostgreSQL sem indice (ANALYZE feito)
runs_pg = []
for i in range(3):
    t0 = time.time()
    cur.execute(QUERY)
    cur.fetchall()
    runs_pg.append((time.time() - t0) * 1000)
avg_pg = sum(runs_pg) / len(runs_pg)
benchmarks.append(("PostgreSQL 15 (row store)", f"{avg_pg:.1f} ms", "OLTP, row-oriented"))

print(f"\n  Query: receita mensal + pedidos + avaliacao (3 execucoes)")
print(f"\n  {'Engine':<30} {'Tempo medio':>14}  {'Obs'}")
print(f"  {'-'*30} {'-'*14}  {'-'*25}")
for name, tempo, obs in benchmarks:
    print(f"  {name:<30} {tempo:>14}  {obs}")

ratio = avg_pg / avg_duck if avg_duck > 0 else 0
print(f"\n  DuckDB e {ratio:.1f}x mais rapido para esta query OLAP.")
print(f"  PostgreSQL e ideal para OLTP (insercoes/atualizacoes frequentes).")
print(f"  DuckDB e ideal para analytics (leitura, agregacoes, BI).")

duck.close()
cur.close()
pg.close()

print("\n" + "=" * 60)
print("  Bonus PostgreSQL concluido!")
print("=" * 60)
