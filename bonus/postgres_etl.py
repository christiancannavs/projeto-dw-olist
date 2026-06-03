"""
bonus/postgres_etl.py
Bonus: carrega o DW no PostgreSQL e compara performance com DuckDB.
Pre-requisitos:
  pip install psycopg2-binary duckdb pandas
  PostgreSQL instalado e rodando

Uso:
  $env:PG_CONN="host=localhost dbname=postgres user=postgres password=SUASENHA port=5432"
  python bonus/postgres_etl.py
"""
import os, sys, time
import duckdb
import pandas as pd
import numpy as np

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("ERRO: pip install psycopg2-binary")
    sys.exit(1)

CONN_STR = os.getenv("PG_CONN", "host=localhost dbname=postgres user=postgres password=postgres port=5432")
BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DUCK  = os.path.join(BASE, "olist_dw.duckdb")

print("=" * 60)
print("  BONUS: PostgreSQL ETL + Comparacao de Performance")
print("=" * 60)

if not os.path.exists(DB_DUCK):
    print(f"ERRO: {DB_DUCK} nao encontrado. Rode setup_dw.py primeiro.")
    sys.exit(1)

duck = duckdb.connect(DB_DUCK, read_only=True)

try:
    pg  = psycopg2.connect(CONN_STR)
    pg.autocommit = False
    cur = pg.cursor()
    print(f"\nPostgreSQL: conectado!")
    cur.execute("SELECT version()")
    print(f"  {cur.fetchone()[0][:70]}")
except Exception as e:
    print(f"\nERRO ao conectar PostgreSQL: {e}")
    print("Defina: $env:PG_CONN=\"host=localhost dbname=postgres user=postgres password=SUASENHA port=5432\"")
    sys.exit(1)

# ── DDL ───────────────────────────────────────────────────────────
print("\n[1] Criando estrutura no PostgreSQL...")
cur.execute("""
DROP TABLE IF EXISTS fact_sales CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_seller CASCADE;

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
    scd_start_date DATE NOT NULL, scd_end_date DATE,
    scd_is_current BOOLEAN NOT NULL DEFAULT TRUE
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
    price NUMERIC(10,2), freight_value NUMERIC(10,2), total_revenue NUMERIC(10,2),
    payment_value NUMERIC(10,2), payment_type VARCHAR(30),
    review_score INTEGER, order_status VARCHAR(20),
    days_to_delivery INTEGER, days_estimated INTEGER, delivery_delay INTEGER,
    PRIMARY KEY (order_id, order_item_id)
);
""")
pg.commit()
print("   DDL criado.")

# ── Funcao de carga ───────────────────────────────────────────────
def load_table(table_name, df, pg_conn):
    """Insere DataFrame no PostgreSQL convertendo tipos numpy para Python nativo."""
    cur2 = pg_conn.cursor()
    cols = list(df.columns)

    def convert(v):
        """Converte qualquer tipo numpy/Decimal/NaT para Python nativo."""
        # NaT (pandas null para datas) e NaN viram None
        if v is None:
            return None
        if isinstance(v, float) and np.isnan(v):
            return None
        # pd.NaT e qualquer Timestamp invalido
        if pd.isnull(v) if not isinstance(v, (list, dict)) else False:
            return None
        # numpy integers
        if isinstance(v, np.integer):
            return int(v)
        # numpy floats
        if isinstance(v, np.floating):
            return float(v)
        # numpy bool
        if isinstance(v, np.bool_):
            return bool(v)
        # pandas Timestamp -> Python date/datetime
        if isinstance(v, pd.Timestamp):
            if pd.isnull(v):
                return None
            return v.date() if v.hour == 0 and v.minute == 0 and v.second == 0 else v.to_pydatetime()
        # fallback numpy scalar
        if hasattr(v, 'item'):
            return v.item()
        return v

    vals = [
        tuple(convert(row[col]) for col in cols)
        for _, row in df.iterrows()
    ]

    query = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES %s ON CONFLICT DO NOTHING"
    execute_values(cur2, query, vals, page_size=2000)
    pg_conn.commit()
    cur2.close()

# ── Carga ─────────────────────────────────────────────────────────
print("\n[2] Carregando tabelas no PostgreSQL...")
t0 = time.time()

tables = ["dim_date", "dim_customer", "dim_product", "dim_seller", "fact_sales"]
for tbl in tables:
    t1 = time.time()
    print(f"   {tbl}...", end=" ", flush=True)
    df = duck.execute(f"SELECT * FROM {tbl}").df()
    load_table(tbl, df, pg)
    print(f"{len(df):,} linhas ({time.time()-t1:.1f}s)")

print(f"\n   Carga total: {time.time()-t0:.1f}s")

# ── Indices ───────────────────────────────────────────────────────
print("\n[3] Criando indices no PostgreSQL...")
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_fact_date     ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_product  ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_status   ON fact_sales(order_status);
ANALYZE fact_sales;
""")
pg.commit()
print("   Indices criados.")

# ── Comparacao de performance ─────────────────────────────────────
print("\n[4] Comparacao de performance: DuckDB vs PostgreSQL")
print("-" * 60)

Q_DUCK = """
    SELECT d.year AS ano, d.month AS mes,
        COUNT(DISTINCT f.order_id) AS pedidos,
        ROUND(SUM(f.price), 2)     AS receita,
        ROUND(AVG(f.review_score), 2) AS avaliacao
    FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status NOT IN ('canceled','unavailable')
    GROUP BY d.year, d.month ORDER BY d.year, d.month
"""

Q_PG = """
    SELECT EXTRACT(YEAR FROM d.full_date) AS ano,
           EXTRACT(MONTH FROM d.full_date) AS mes,
           COUNT(DISTINCT f.order_id)  AS pedidos,
           ROUND(SUM(f.price)::numeric, 2) AS receita,
           ROUND(AVG(f.review_score)::numeric, 2) AS avaliacao
    FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status NOT IN ('canceled','unavailable')
    GROUP BY 1, 2 ORDER BY 1, 2
"""

def bench(fn, n=3):
    times = []
    for _ in range(n):
        t = time.time()
        fn()
        times.append((time.time() - t) * 1000)
    return sum(times) / len(times)

avg_duck = bench(lambda: duck.execute(Q_DUCK).df())
avg_pg   = bench(lambda: (cur.execute(Q_PG), cur.fetchall()))

print(f"\n  Query: receita mensal + pedidos + avaliacao ({3} execucoes cada)")
print(f"\n  {'Engine':<35} {'Tempo medio':>12}  Caracteristica")
print(f"  {'-'*35} {'-'*12}  {'-'*28}")
print(f"  {'DuckDB 1.5.3 (colunar, OLAP)':<35} {avg_duck:>10.1f}ms  Nativo para analytics")
print(f"  {'PostgreSQL 18 (row store, OLTP)':<35} {avg_pg:>10.1f}ms  Nativo para transacoes")

ratio = avg_pg / avg_duck if avg_duck > 0 else 0
print(f"\n  Conclusao: DuckDB e {ratio:.1f}x mais rapido para esta query OLAP.")
print(f"  PostgreSQL e ideal para insercoes/atualizacoes frequentes (OLTP).")
print(f"  DuckDB e ideal para leitura analitica em larga escala (OLAP/BI).")

# ── Validacao ─────────────────────────────────────────────────────
print("\n[5] Validacao de contagens")
print(f"  {'Tabela':<20} {'DuckDB':>10} {'PostgreSQL':>12} {'Status':>8}")
print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*8}")
for tbl in tables:
    n_duck = duck.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    n_pg = cur.fetchone()[0]
    status = "OK" if n_duck == n_pg else "DIVERGE"
    print(f"  {tbl:<20} {n_duck:>10,} {n_pg:>12,} {status:>8}")

duck.close()
cur.close()
pg.close()

print("\n" + "=" * 60)
print("  Bonus PostgreSQL concluido com sucesso!")
print("=" * 60)
