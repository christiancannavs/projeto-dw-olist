"""
gerar_graficos.py
Gera os 4 gráficos do projeto DW Olist a partir do banco DuckDB.
Uso: python gerar_graficos.py
"""
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

DB  = os.path.join(os.path.dirname(__file__), '..', 'olist_dw.duckdb')
OUT = os.path.dirname(__file__)

conn = duckdb.connect(DB)

q1 = conn.execute("""
SELECT d.year AS ano, d.month AS mes,
    COUNT(DISTINCT f.order_id) AS total_pedidos,
    ROUND(SUM(f.total_revenue), 2) AS receita_total,
    ROUND(AVG(f.price), 2) AS ticket_medio_item
FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
WHERE f.order_status NOT IN ('canceled','unavailable') AND d.year >= 2017
  AND f.total_pedidos > 50
GROUP BY d.year, d.month ORDER BY d.year, d.month
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
        EXTRACT('year' FROM MIN(d.full_date)) AS ano,
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

# --- Gráfico 1 ---
q1['periodo'] = q1['ano'].astype(str) + "-" + q1['mes'].astype(str).str.zfill(2)
fig1 = make_subplots(specs=[[{"secondary_y": True}]])
fig1.add_trace(go.Scatter(x=q1['periodo'], y=q1['receita_total'], name="Receita (R$)",
    line=dict(color="#7B2FBE", width=3), fill='tozeroy', fillcolor='rgba(123,47,190,0.1)'), secondary_y=False)
fig1.add_trace(go.Scatter(x=q1['periodo'], y=q1['total_pedidos'], name="Pedidos",
    line=dict(color="#FF6B35", width=2, dash='dot'), mode='lines+markers'), secondary_y=True)
fig1.update_layout(title="<b>Evolução de Vendas Mensais — Olist 2017–2018</b>",
    plot_bgcolor='white', paper_bgcolor='white', height=480)
fig1.write_image(f"{OUT}/grafico_1_evolucao_vendas.png", scale=2, width=900, height=480)

# --- Gráfico 2 ---
q2s = q2.sort_values('receita_total')
q2s['categoria_fmt'] = q2s['categoria'].str.replace('_', ' ').str.title()
fig2 = px.bar(q2s, x='receita_total', y='categoria_fmt', orientation='h',
    text=q2s['receita_total'].apply(lambda x: f"R$ {x/1e6:.2f}M"),
    color='receita_total', color_continuous_scale='Purples')
fig2.update_traces(textposition='outside')
fig2.update_layout(title="<b>Top 10 Categorias por Receita</b>",
    plot_bgcolor='white', paper_bgcolor='white', coloraxis_showscale=False,
    height=500, margin=dict(l=200, r=120))
fig2.write_image(f"{OUT}/grafico_2_top_categorias.png", scale=2, width=950, height=500)

# --- Gráfico 3 ---
top_cats = q3.groupby('categoria')['receita_total'].sum().nlargest(10).index.tolist()
top_states = ['SP','RJ','MG','RS','PR','SC','BA','GO','PE','DF']
heat_df = q3[q3['categoria'].isin(top_cats) & q3['estado'].isin(top_states)]
pivot = heat_df.pivot_table(values='receita_total', index='categoria', columns='estado', fill_value=0)
pivot.index = pivot.index.str.replace('_',' ').str.title()
fig3 = go.Figure(data=go.Heatmap(z=pivot.values/1000, x=pivot.columns.tolist(), y=pivot.index.tolist(),
    colorscale='Purples', texttemplate="%{z:.0f}k", textfont={"size": 9}))
fig3.update_layout(title="<b>Receita por Categoria × Estado (R$ mil)</b>",
    plot_bgcolor='white', paper_bgcolor='white', height=520, margin=dict(l=210))
fig3.write_image(f"{OUT}/grafico_3_heatmap.png", scale=2, width=950, height=520)

# --- Gráfico 4 dashboard ---
q4['periodo'] = q4['ano'].astype(str) + "-" + q4['mes'].astype(str).str.zfill(2)
top10 = q5.nlargest(10, 'ticket_medio').sort_values('ticket_medio')
fig4 = make_subplots(rows=2, cols=2,
    subplot_titles=("Novos Clientes por Mês","Ticket Médio por Estado (Top 10)",
                    "Prazo Médio de Entrega","% Retenção de Clientes"))
fig4.add_trace(go.Bar(x=q4['periodo'], y=q4['novos_clientes'], marker_color='#7B2FBE', showlegend=False), row=1, col=1)
fig4.add_trace(go.Bar(x=top10['ticket_medio'], y=top10['estado'], orientation='h', marker_color='#FF6B35', showlegend=False), row=1, col=2)
q5_prazo = q5.dropna(subset=['prazo_medio_dias']).sort_values('prazo_medio_dias', ascending=False).head(15)
fig4.add_trace(go.Bar(x=q5_prazo['estado'], y=q5_prazo['prazo_medio_dias'], marker_color='#2E86AB', showlegend=False), row=2, col=1)
fig4.add_trace(go.Scatter(x=q4['periodo'], y=q4['pct_retencao'], mode='lines+markers',
    line=dict(color='#F72585', width=2), showlegend=False), row=2, col=2)
fig4.update_layout(title="<b>Dashboard Executivo — Olist E-Commerce</b>",
    plot_bgcolor='white', paper_bgcolor='white', height=700)
fig4.write_image(f"{OUT}/grafico_4_dashboard.png", scale=2, width=1100, height=700)

print("Graficos gerados!")
