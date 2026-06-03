"""
gerar_graficos.py
Gera os 4 graficos do projeto DW Olist.
Uso: python visualizacoes/gerar_graficos.py
"""
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, '..', 'olist_dw.duckdb')
OUT  = BASE

print(f"Conectando em: {os.path.abspath(DB)}")
conn = duckdb.connect(DB)

print("Extraindo dados...")

q1 = conn.execute("""
SELECT d.year AS ano, d.month AS mes,
    COUNT(DISTINCT f.order_id) AS total_pedidos,
    ROUND(SUM(f.total_revenue), 2) AS receita_total,
    ROUND(AVG(f.price), 2) AS ticket_medio_item
FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status NOT IN ('canceled','unavailable') AND d.year >= 2017
GROUP BY d.year, d.month
HAVING COUNT(DISTINCT f.order_id) > 50
ORDER BY d.year, d.month
""").df()

q2 = conn.execute("""
SELECT p.product_category AS categoria,
    ROUND(SUM(f.price), 2) AS receita_total,
    COUNT(DISTINCT f.order_id) AS total_pedidos
FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
WHERE f.order_status NOT IN ('canceled','unavailable')
GROUP BY p.product_category ORDER BY receita_total DESC LIMIT 10
""").df()

q3 = conn.execute("""
SELECT p.product_category AS categoria, c.customer_state AS estado,
    ROUND(SUM(f.price), 2) AS receita_total
FROM fact_sales f
JOIN dim_product p ON f.product_key = p.product_key
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.order_status NOT IN ('canceled','unavailable')
GROUP BY p.product_category, c.customer_state
""").df()

q4 = conn.execute("""
WITH pc AS (
    SELECT dc.customer_unique_id,
        EXTRACT('year'  FROM MIN(d.full_date)) AS ano,
        EXTRACT('month' FROM MIN(d.full_date)) AS mes
    FROM fact_sales f
    JOIN dim_customer dc ON f.customer_key = dc.customer_key
    JOIN dim_date d ON f.date_key = d.date_key
    WHERE f.order_status NOT IN ('canceled','unavailable')
    GROUP BY dc.customer_unique_id
),
tp AS (
    SELECT dc.customer_unique_id, COUNT(DISTINCT f.order_id) AS total_pedidos
    FROM fact_sales f JOIN dim_customer dc ON f.customer_key = dc.customer_key
    GROUP BY dc.customer_unique_id
)
SELECT pc.ano::INTEGER AS ano, pc.mes::INTEGER AS mes,
    COUNT(*) AS novos_clientes,
    ROUND(COUNT(CASE WHEN tp.total_pedidos > 1 THEN 1 END)*100.0/COUNT(*),2) AS pct_retencao
FROM pc LEFT JOIN tp ON pc.customer_unique_id = tp.customer_unique_id
WHERE pc.ano >= 2017
GROUP BY pc.ano, pc.mes ORDER BY pc.ano, pc.mes
""").df()

q5 = conn.execute("""
SELECT c.customer_state AS estado,
    ROUND(AVG(f.price),2) AS ticket_medio,
    ROUND(AVG(f.days_to_delivery),1) AS prazo_medio_dias
FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.order_status NOT IN ('canceled','unavailable')
GROUP BY c.customer_state ORDER BY ticket_medio DESC
""").df()

conn.close()
print("Dados extraidos. Gerando graficos...\n")

# ── Grafico 1: Linha — evolucao mensal ────────────────────────────
q1['periodo'] = q1['ano'].astype(str) + "-" + q1['mes'].astype(str).str.zfill(2)

fig1 = make_subplots(specs=[[{"secondary_y": True}]])
fig1.add_trace(go.Scatter(
    x=q1['periodo'], y=q1['receita_total'],
    name="Receita Total (R$)",
    line=dict(color="#7B2FBE", width=3),
    fill='tozeroy', fillcolor='rgba(123,47,190,0.1)'
), secondary_y=False)
fig1.add_trace(go.Scatter(
    x=q1['periodo'], y=q1['total_pedidos'],
    name="Numero de Pedidos",
    line=dict(color="#FF6B35", width=2, dash='dot'),
    mode='lines+markers', marker=dict(size=6)
), secondary_y=True)
fig1.update_layout(
    title=dict(text="<b>Evolucao de Vendas Mensais — Olist 2017-2018</b>", font=dict(size=18), x=0.5),
    plot_bgcolor='white', paper_bgcolor='white', hovermode='x unified',
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(title="Periodo", gridcolor='#f0f0f0', tickangle=-45),
    height=480
)
fig1.update_yaxes(title_text="Receita Total (R$)", secondary_y=False, tickprefix="R$ ", gridcolor='#f0f0f0')
fig1.update_yaxes(title_text="Numero de Pedidos", secondary_y=True)
p1 = os.path.join(OUT, 'grafico_1_evolucao_vendas.png')
fig1.write_image(p1, scale=2, width=900, height=480)
print(f"  Grafico 1 salvo: {p1}")

# ── Grafico 2: Barras — top 10 categorias ─────────────────────────
q2s = q2.sort_values('receita_total')
q2s['categoria_fmt'] = q2s['categoria'].str.replace('_', ' ').str.title()

fig2 = px.bar(q2s, x='receita_total', y='categoria_fmt', orientation='h',
    text=q2s['receita_total'].apply(lambda x: f"R$ {x/1e6:.2f}M"),
    color='receita_total', color_continuous_scale='Purples')
fig2.update_traces(textposition='outside', textfont_size=11)
fig2.update_layout(
    title=dict(text="<b>Top 10 Categorias por Receita Total</b>", font=dict(size=18), x=0.5),
    xaxis_title="Receita Total (R$)", yaxis_title="Categoria",
    plot_bgcolor='white', paper_bgcolor='white',
    coloraxis_showscale=False, height=500, margin=dict(l=200, r=120)
)
fig2.update_xaxes(gridcolor='#f0f0f0', tickprefix="R$ ")
p2 = os.path.join(OUT, 'grafico_2_top_categorias.png')
fig2.write_image(p2, scale=2, width=950, height=500)
print(f"  Grafico 2 salvo: {p2}")

# ── Grafico 3: Mapa de calor categoria x estado ───────────────────
top_cats   = q3.groupby('categoria')['receita_total'].sum().nlargest(10).index.tolist()
top_states = ['SP','RJ','MG','RS','PR','SC','BA','GO','PE','DF']
heat_df = q3[q3['categoria'].isin(top_cats) & q3['estado'].isin(top_states)]
pivot = heat_df.pivot_table(values='receita_total', index='categoria', columns='estado', fill_value=0)
pivot.index = pivot.index.str.replace('_', ' ').str.title()

fig3 = go.Figure(data=go.Heatmap(
    z=pivot.values / 1000,
    x=pivot.columns.tolist(), y=pivot.index.tolist(),
    colorscale='Purples',
    text=[[f"R${v:.0f}k" if v > 0 else "" for v in row] for row in pivot.values/1000],
    texttemplate="%{text}", textfont={"size": 9},
    hovertemplate="Estado: %{x}<br>Categoria: %{y}<br>R$ %{z:.1f}k<extra></extra>"
))
fig3.update_layout(
    title=dict(text="<b>Receita por Categoria x Estado (R$ mil)</b>", font=dict(size=18), x=0.5),
    xaxis_title="Estado", yaxis_title="Categoria",
    plot_bgcolor='white', paper_bgcolor='white', height=520, margin=dict(l=210)
)
p3 = os.path.join(OUT, 'grafico_3_heatmap.png')
fig3.write_image(p3, scale=2, width=950, height=520)
print(f"  Grafico 3 salvo: {p3}")

# ── Grafico 4: Dashboard composto ────────────────────────────────
q4['periodo'] = q4['ano'].astype(str) + "-" + q4['mes'].astype(str).str.zfill(2)
top10 = q5.nlargest(10, 'ticket_medio').sort_values('ticket_medio')

fig4 = make_subplots(rows=2, cols=2,
    subplot_titles=(
        "Novos Clientes por Mes (Cohort)",
        "Ticket Medio por Estado (Top 10)",
        "Prazo Medio de Entrega (dias)",
        "% Retencao de Clientes"
    ),
    vertical_spacing=0.18, horizontal_spacing=0.12
)
fig4.add_trace(go.Bar(
    x=q4['periodo'], y=q4['novos_clientes'],
    marker_color='#7B2FBE', showlegend=False
), row=1, col=1)
fig4.add_trace(go.Bar(
    x=top10['ticket_medio'], y=top10['estado'],
    orientation='h', marker_color='#FF6B35', showlegend=False,
    text=[f"R$ {v:.0f}" for v in top10['ticket_medio']], textposition='outside'
), row=1, col=2)
q5_prazo = q5.dropna(subset=['prazo_medio_dias']).sort_values('prazo_medio_dias', ascending=False).head(15)
fig4.add_trace(go.Bar(
    x=q5_prazo['estado'], y=q5_prazo['prazo_medio_dias'],
    marker_color='#2E86AB', showlegend=False
), row=2, col=1)
fig4.add_trace(go.Scatter(
    x=q4['periodo'], y=q4['pct_retencao'],
    mode='lines+markers', line=dict(color='#F72585', width=2),
    marker=dict(size=8), showlegend=False
), row=2, col=2)
fig4.update_layout(
    title=dict(text="<b>Cohort, KPI por Estado</b>", font=dict(size=20), x=0.5),
    plot_bgcolor='white', paper_bgcolor='white', height=700
)
fig4.update_xaxes(gridcolor='#f0f0f0')
fig4.update_yaxes(gridcolor='#f0f0f0')
p4 = os.path.join(OUT, 'grafico_4.png')
fig4.write_image(p4, scale=2, width=1100, height=700)
print(f"  Grafico 4 salvo: {p4}")

print("\nTodos os 4 graficos gerados com sucesso!")
