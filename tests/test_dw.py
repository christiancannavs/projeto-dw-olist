"""
tests/test_dw.py
Testes automatizados de integridade do Data Warehouse Olist.
Uso: python tests/test_dw.py
"""
import duckdb
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "olist_dw.duckdb")

VERDE   = "\033[92m"
VERMELHO = "\033[91m"
RESET   = "\033[0m"
AMARELO = "\033[93m"

passed = 0
failed = 0
results = []

def check(nome, condicao, detalhe=""):
    global passed, failed
    if condicao:
        passed += 1
        results.append(f"  {VERDE}PASS{RESET}  {nome}")
    else:
        failed += 1
        results.append(f"  {VERMELHO}FAIL{RESET}  {nome}" + (f"\n         {AMARELO}→ {detalhe}{RESET}" if detalhe else ""))

print("=" * 60)
print("  TESTES DE INTEGRIDADE — Data Warehouse Olist")
print("=" * 60)

if not os.path.exists(DB):
    print(f"\n{VERMELHO}ERRO: Banco nao encontrado em {DB}{RESET}")
    print("Execute primeiro: python setup_dw.py")
    sys.exit(1)

conn = duckdb.connect(DB, read_only=True)

# ── 1. CONTAGEM DE LINHAS ────────────────────────────────────────
print("\n[1] Contagem de linhas minimas")

n_date = conn.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
check("dim_date tem pelo menos 1.000 dias", n_date >= 1000, f"encontrado: {n_date}")

n_cust = conn.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
check("dim_customer tem pelo menos 90.000 clientes", n_cust >= 90000, f"encontrado: {n_cust}")

n_prod = conn.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0]
check("dim_product tem pelo menos 30.000 produtos", n_prod >= 30000, f"encontrado: {n_prod}")

n_sell = conn.execute("SELECT COUNT(*) FROM dim_seller").fetchone()[0]
check("dim_seller tem pelo menos 3.000 vendedores", n_sell >= 3000, f"encontrado: {n_sell}")

n_fact = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
check("fact_sales tem pelo menos 100.000 itens", n_fact >= 100000, f"encontrado: {n_fact}")

n_ped = conn.execute("SELECT COUNT(DISTINCT order_id) FROM fact_sales").fetchone()[0]
check("fact_sales tem pelo menos 90.000 pedidos unicos", n_ped >= 90000, f"encontrado: {n_ped}")

# ── 2. CHAVES PRIMARIAS ──────────────────────────────────────────
print("\n[2] Unicidade de chaves primarias")

dup_date = conn.execute("SELECT COUNT(*) FROM (SELECT date_key, COUNT(*) FROM dim_date GROUP BY date_key HAVING COUNT(*) > 1)").fetchone()[0]
check("dim_date sem date_key duplicado", dup_date == 0, f"{dup_date} duplicatas")

dup_cust = conn.execute("SELECT COUNT(*) FROM (SELECT customer_key, COUNT(*) FROM dim_customer GROUP BY customer_key HAVING COUNT(*) > 1)").fetchone()[0]
check("dim_customer sem customer_key duplicado", dup_cust == 0, f"{dup_cust} duplicatas")

dup_prod = conn.execute("SELECT COUNT(*) FROM (SELECT product_key, COUNT(*) FROM dim_product GROUP BY product_key HAVING COUNT(*) > 1)").fetchone()[0]
check("dim_product sem product_key duplicado", dup_prod == 0, f"{dup_prod} duplicatas")

dup_fact = conn.execute("SELECT COUNT(*) FROM (SELECT order_id, order_item_id, COUNT(*) FROM fact_sales GROUP BY order_id, order_item_id HAVING COUNT(*) > 1)").fetchone()[0]
check("fact_sales sem (order_id, order_item_id) duplicado", dup_fact == 0, f"{dup_fact} duplicatas")

# ── 3. INTEGRIDADE REFERENCIAL ───────────────────────────────────
print("\n[3] Integridade referencial (FK -> PK)")

orphan_date = conn.execute("""
    SELECT COUNT(*) FROM fact_sales f
    WHERE NOT EXISTS (SELECT 1 FROM dim_date d WHERE d.date_key = f.date_key)
""").fetchone()[0]
check("Todos os date_key da fato existem em dim_date", orphan_date == 0, f"{orphan_date} orfaos")

orphan_cust = conn.execute("""
    SELECT COUNT(*) FROM fact_sales f
    WHERE NOT EXISTS (SELECT 1 FROM dim_customer c WHERE c.customer_key = f.customer_key)
""").fetchone()[0]
check("Todos os customer_key da fato existem em dim_customer", orphan_cust == 0, f"{orphan_cust} orfaos")

orphan_prod = conn.execute("""
    SELECT COUNT(*) FROM fact_sales f
    WHERE NOT EXISTS (SELECT 1 FROM dim_product p WHERE p.product_key = f.product_key)
""").fetchone()[0]
check("Todos os product_key da fato existem em dim_product", orphan_prod == 0, f"{orphan_prod} orfaos")

orphan_sell = conn.execute("""
    SELECT COUNT(*) FROM fact_sales f
    WHERE NOT EXISTS (SELECT 1 FROM dim_seller s WHERE s.seller_key = f.seller_key)
""").fetchone()[0]
check("Todos os seller_key da fato existem em dim_seller", orphan_sell == 0, f"{orphan_sell} orfaos")

# ── 4. NULLS EM CAMPOS OBRIGATORIOS ──────────────────────────────
print("\n[4] Campos obrigatorios sem NULL")

null_price = conn.execute("SELECT COUNT(*) FROM fact_sales WHERE price IS NULL").fetchone()[0]
check("fact_sales.price sem NULL", null_price == 0, f"{null_price} nulos")

null_rev = conn.execute("SELECT COUNT(*) FROM fact_sales WHERE total_revenue IS NULL").fetchone()[0]
check("fact_sales.total_revenue sem NULL", null_rev == 0, f"{null_rev} nulos")

null_state = conn.execute("SELECT COUNT(*) FROM dim_customer WHERE customer_state IS NULL").fetchone()[0]
check("dim_customer.customer_state sem NULL", null_state == 0, f"{null_state} nulos")

null_cat = conn.execute("SELECT COUNT(*) FROM dim_product WHERE product_category IS NULL").fetchone()[0]
check("dim_product.product_category sem NULL", null_cat == 0, f"{null_cat} nulos")

# ── 5. VALORES INVALIDOS ─────────────────────────────────────────
print("\n[5] Validacao de valores")

neg_price = conn.execute("SELECT COUNT(*) FROM fact_sales WHERE price < 0").fetchone()[0]
check("Nenhum preco negativo na fato", neg_price == 0, f"{neg_price} precos negativos")

neg_freight = conn.execute("SELECT COUNT(*) FROM fact_sales WHERE freight_value < 0").fetchone()[0]
check("Nenhum frete negativo na fato", neg_freight == 0, f"{neg_freight} fretes negativos")

bad_score = conn.execute("SELECT COUNT(*) FROM fact_sales WHERE review_score IS NOT NULL AND review_score NOT BETWEEN 1 AND 5").fetchone()[0]
check("Avaliacoes fora do range 1-5 ausentes", bad_score == 0, f"{bad_score} notas invalidas")

bad_date_key = conn.execute("SELECT COUNT(*) FROM dim_date WHERE date_key != CAST(strftime(full_date, '%Y%m%d') AS INTEGER)").fetchone()[0]
check("date_key consistente com full_date (formato YYYYMMDD)", bad_date_key == 0, f"{bad_date_key} inconsistencias")

# ── 6. SCD TYPE 2 ────────────────────────────────────────────────
print("\n[6] SCD Type 2 — dim_customer")

multi_current = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT customer_unique_id, COUNT(*) FROM dim_customer
        WHERE scd_is_current = TRUE
        GROUP BY customer_unique_id HAVING COUNT(*) > 1
    )
""").fetchone()[0]
check("Cada cliente tem no maximo 1 registro current", multi_current == 0, f"{multi_current} clientes com multiplos current")

pct_current = conn.execute("""
    SELECT ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dim_customer), 2)
    FROM dim_customer WHERE scd_is_current = TRUE
""").fetchone()[0]
check("Pelo menos 99% dos registros sao current (base sem historico)", float(pct_current) >= 99.0, f"apenas {pct_current}% current")

# ── 7. METRICAS DE NEGOCIO ───────────────────────────────────────
print("\n[7] Sanidade das metricas de negocio")

receita = conn.execute("""
    SELECT ROUND(SUM(total_revenue), 2) FROM fact_sales
    WHERE order_status NOT IN ('canceled','unavailable')
""").fetchone()[0]
check("Receita total entre R$10M e R$20M (esperado ~R$15.7M)", 10_000_000 <= float(receita) <= 20_000_000, f"encontrado: R$ {receita:,.2f}")

avg_ticket = conn.execute("SELECT ROUND(AVG(price), 2) FROM fact_sales WHERE price > 0").fetchone()[0]
check("Ticket medio entre R$50 e R$300 (esperado ~R$120)", 50 <= float(avg_ticket) <= 300, f"encontrado: R$ {avg_ticket}")

avg_score = conn.execute("SELECT ROUND(AVG(review_score), 2) FROM fact_sales WHERE review_score IS NOT NULL").fetchone()[0]
check("Avaliacao media entre 3.5 e 5.0 (esperado ~4.04)", 3.5 <= float(avg_score) <= 5.0, f"encontrado: {avg_score}")

pct_delivered = conn.execute("""
    SELECT ROUND(COUNT(CASE WHEN order_status = 'delivered' THEN 1 END) * 100.0 / COUNT(*), 1)
    FROM fact_sales
""").fetchone()[0]
check("Pelo menos 90% dos itens com status 'delivered'", float(pct_delivered) >= 90.0, f"encontrado: {pct_delivered}%")

conn.close()

# ── RESULTADO FINAL ──────────────────────────────────────────────
print()
for r in results:
    print(r)

total = passed + failed
print()
print("=" * 60)
print(f"  Resultado: {passed}/{total} testes passaram", end="")
if failed == 0:
    print(f"  {VERDE}TODOS OK!{RESET}")
else:
    print(f"  {VERMELHO}{failed} FALHA(S){RESET}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
