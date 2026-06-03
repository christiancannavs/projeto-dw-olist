"""
dashboard_streamlit.py
Dashboard interativo do projeto DW Olist.
Uso local  : streamlit run dashboard_streamlit.py
Deploy     : https://streamlit.io/cloud (conecte o repositorio GitHub)
"""
import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ── Config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Olist DW Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(BASE, "olist_dw.duckdb")

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; }
.block-container { padding-top: 1.5rem; }
h1 { font-size: 1.6rem !important; }
h2 { font-size: 1.1rem !important; color: #7B2FBE; }
</style>
""", unsafe_allow_html=True)

# ── Conexao ───────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    if not os.path.exists(DB):
        st.error(f"Banco nao encontrado: {DB}\nExecute setup_dw.py primeiro.")
        st.stop()
    return duckdb.connect(DB, read_only=True)

conn = get_conn()

# ── Queries cacheadas ─────────────────────────────────────────────
@st.cache_data
def load_monthly():
    return conn.execute("""
        SELECT d.year AS ano, d.month AS mes,
            d.month_name AS nome_mes,
            COUNT(DISTINCT f.order_id) AS pedidos,
            ROUND(SUM(f.price), 2)         AS receita,
            ROUND(AVG(f.review_score), 3)  AS avaliacao
        FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
        WHERE f.order_status NOT IN ('canceled','unavailable')
          AND d.year BETWEEN 2017 AND 2018
        GROUP BY d.year, d.month, d.month_name
        HAVING COUNT(DISTINCT f.order_id) > 50
        ORDER BY d.year, d.month
    """).df()

@st.cache_data
def load_cats():
    return conn.execute("""
        SELECT p.product_category AS categoria,
            COUNT(DISTINCT f.order_id) AS pedidos,
            ROUND(SUM(f.price), 2)     AS receita,
            ROUND(AVG(f.price), 2)     AS ticket_medio,
            ROUND(AVG(f.review_score), 2) AS avaliacao
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        WHERE f.order_status NOT IN ('canceled','unavailable')
        GROUP BY p.product_category ORDER BY receita DESC
    """).df()

@st.cache_data
def load_states():
    return conn.execute("""
        SELECT c.customer_state AS estado,
            COUNT(DISTINCT f.order_id)  AS pedidos,
            ROUND(SUM(f.price), 2)      AS receita,
            ROUND(AVG(f.price), 2)      AS ticket_medio,
            ROUND(AVG(f.review_score), 2) AS avaliacao,
            ROUND(AVG(f.days_to_delivery), 1) AS prazo_dias,
            ROUND(
                COUNT(CASE WHEN COALESCE(f.delivery_delay,0) <= 0 THEN 1 END) * 100.0
                / NULLIF(COUNT(f.days_to_delivery), 0), 1) AS pct_prazo
        FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE f.order_status NOT IN ('canceled','unavailable')
        GROUP BY c.customer_state ORDER BY receita DESC
    """).df()

@st.cache_data
def load_payments():
    return conn.execute("""
        SELECT payment_type AS tipo,
            COUNT(*)               AS qtd,
            ROUND(SUM(total_revenue), 2) AS receita
        FROM fact_sales
        WHERE order_status NOT IN ('canceled','unavailable')
          AND payment_type IS NOT NULL
        GROUP BY payment_type ORDER BY receita DESC
    """).df()

@st.cache_data
def load_reviews():
    return conn.execute("""
        SELECT review_score AS nota, COUNT(*) AS qtd
        FROM fact_sales WHERE review_score IS NOT NULL
        GROUP BY review_score ORDER BY review_score
    """).df()

@st.cache_data
def load_kpis():
    return conn.execute("""
        SELECT
            COUNT(DISTINCT order_id)           AS total_pedidos,
            ROUND(SUM(price), 2)               AS receita_total,
            ROUND(AVG(price), 2)               AS ticket_medio,
            ROUND(AVG(review_score), 2)        AS avaliacao_media,
            ROUND(AVG(days_to_delivery), 1)    AS prazo_medio,
            COUNT(DISTINCT customer_key)       AS clientes_unicos
        FROM fact_sales
        WHERE order_status NOT IN ('canceled','unavailable')
    """).fetchone()

monthly  = load_monthly()
cats     = load_cats()
states   = load_states()
payments = load_payments()
reviews  = load_reviews()
kpis     = load_kpis()

PURPLE = "#7B2FBE"
ORANGE = "#FF6B35"
BLUE   = "#2E86AB"
PINK   = "#F72585"
PAY_COLORS = [PURPLE, "#1D9E75", ORANGE, PINK]

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Olist_logo.svg/320px-Olist_logo.svg.png",
             width=140)
    st.markdown("## Filtros")

    anos = ["Todos", "2017", "2018"]
    ano_sel = st.selectbox("Ano", anos)

    categorias_lista = ["Todas"] + sorted(cats['categoria'].tolist())
    cat_sel = st.selectbox("Categoria", categorias_lista)

    estados_lista = ["Todos"] + sorted(states['estado'].tolist())
    estado_sel = st.selectbox("Estado", estados_lista)

    st.divider()
    st.markdown("**Sobre o projeto**")
    st.caption("Data Warehouse construído com DuckDB sobre o dataset público Olist (Kaggle). Projeto acadêmico — FATEC Jundiaí.")

# ── Filtragem ─────────────────────────────────────────────────────
monthly_f = monthly.copy()
if ano_sel != "Todos":
    monthly_f = monthly_f[monthly_f['ano'] == int(ano_sel)]

# ── Header ────────────────────────────────────────────────────────
st.markdown("# 🛒 Olist E-Commerce — Data Warehouse Dashboard")
st.caption("Dataset: Brazilian E-Commerce by Olist (Kaggle) · 2016–2018 · 99 mil pedidos")
st.divider()

# ── KPIs ──────────────────────────────────────────────────────────
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("📦 Pedidos",      f"{int(kpis[0]):,}".replace(",","."))
col2.metric("💰 Receita",      f"R$ {kpis[1]/1e6:.1f}M")
col3.metric("🧾 Ticket médio", f"R$ {kpis[2]:.2f}")
col4.metric("⭐ Avaliação",    f"{kpis[3]:.2f} / 5")
col5.metric("🚚 Prazo médio",  f"{kpis[4]} dias")
col6.metric("👤 Clientes",     f"{int(kpis[5]):,}".replace(",","."))

st.divider()

# ── Linha: evolucao mensal ────────────────────────────────────────
st.markdown("## Evolução mensal de vendas")

metrica_map = {"Receita (R$)": "receita", "Pedidos": "pedidos", "Avaliação": "avaliacao"}
metrica_label = st.radio("Métrica:", list(metrica_map.keys()), horizontal=True)
metrica = metrica_map[metrica_label]

monthly_f['periodo'] = monthly_f['ano'].astype(str) + "-" + monthly_f['mes'].astype(str).str.zfill(2)

fig_line = go.Figure()
color = PURPLE if metrica == "receita" else (ORANGE if metrica == "pedidos" else "#1D9E75")
fig_line.add_trace(go.Scatter(
    x=monthly_f['periodo'], y=monthly_f[metrica],
    mode='lines+markers', line=dict(color=color, width=2.5),
    fill='tozeroy', fillcolor=color + '18',
    marker=dict(size=6),
    hovertemplate='%{x}: %{y:,.0f}<extra></extra>'
))
fig_line.update_layout(
    height=320, margin=dict(t=10, b=10),
    plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(gridcolor='#f0f0f0', tickangle=-45),
    yaxis=dict(gridcolor='#f0f0f0',
               tickprefix="R$ " if metrica == "receita" else "")
)
st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# ── Duas colunas: categorias + pagamento/avaliacoes ────────────────
col_a, col_b = st.columns([1.4, 1])

with col_a:
    st.markdown("## Top categorias")
    n_cats = st.slider("Quantas categorias", 5, 15, 10)
    metric_cat = st.radio("Ordenar por:", ["receita", "pedidos", "ticket_medio"], horizontal=True)
    top_cats = cats.nlargest(n_cats, metric_cat).sort_values(metric_cat)
    top_cats['label'] = top_cats['categoria'].str.replace('_', ' ').str.title()

    fig_bar = px.bar(top_cats, x=metric_cat, y='label', orientation='h',
        color=metric_cat, color_continuous_scale='Purples',
        labels={metric_cat: metrica_label, 'label': ''})
    fig_bar.update_layout(
        height=380, margin=dict(t=10, b=10),
        plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
        coloraxis_showscale=False,
        xaxis=dict(gridcolor='#f0f0f0', tickprefix="R$ " if metric_cat in ['receita','ticket_medio'] else "")
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_b:
    st.markdown("## Forma de pagamento")
    pay_labels = {'credit_card':'Cartão crédito','boleto':'Boleto','voucher':'Voucher','debit_card':'Cartão débito'}
    payments['label'] = payments['tipo'].map(pay_labels).fillna(payments['tipo'])
    fig_pie = px.pie(payments, values='receita', names='label',
        color_discrete_sequence=PAY_COLORS, hole=0.55)
    fig_pie.update_traces(textposition='outside', textinfo='percent+label')
    fig_pie.update_layout(
        height=220, margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("## Avaliações dos clientes")
    rev_colors = ['#E24B4A','#D85A30','#BA7517','#1D9E75', PURPLE]
    total_rev = reviews['qtd'].sum()
    reviews['pct'] = (reviews['qtd'] / total_rev * 100).round(1)
    fig_rev = px.bar(reviews, x='nota', y='pct',
        color='nota', color_discrete_sequence=rev_colors,
        labels={'nota': 'Nota', 'pct': '% das avaliações'},
        text=reviews['pct'].apply(lambda x: f"{x:.0f}%"))
    fig_rev.update_traces(textposition='outside')
    fig_rev.update_layout(
        height=200, margin=dict(t=10, b=10),
        plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        xaxis=dict(tickvals=[1,2,3,4,5], gridcolor='#f0f0f0'),
        yaxis=dict(gridcolor='#f0f0f0')
    )
    st.plotly_chart(fig_rev, use_container_width=True)

st.divider()

# ── Estados ───────────────────────────────────────────────────────
st.markdown("## KPIs por estado")

col_ord, col_top = st.columns([1, 1])
with col_ord:
    sort_field = st.selectbox("Ordenar por:", {
        "receita": "Receita", "ticket_medio": "Ticket médio",
        "prazo_dias": "Prazo de entrega", "pct_prazo": "% no prazo"
    })
with col_top:
    n_states = st.slider("Quantos estados", 5, 27, 15)

states_sorted = states.sort_values(sort_field, ascending=False).head(n_states)

fig_states = px.bar(
    states_sorted.sort_values(sort_field),
    x=sort_field, y='estado', orientation='h',
    color=sort_field, color_continuous_scale='Purples',
    hover_data=['pedidos', 'ticket_medio', 'prazo_dias', 'pct_prazo'],
    labels={sort_field: sort_field.replace('_', ' ').title(), 'estado': ''}
)
fig_states.update_layout(
    height=max(300, n_states * 28),
    margin=dict(t=10, b=10),
    plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
    coloraxis_showscale=False,
    xaxis=dict(gridcolor='#f0f0f0',
               tickprefix="R$ " if sort_field in ['receita','ticket_medio'] else "")
)
st.plotly_chart(fig_states, use_container_width=True)

# Tabela interativa
with st.expander("Ver tabela completa de estados"):
    st.dataframe(
        states.rename(columns={
            'estado':'UF','pedidos':'Pedidos','receita':'Receita (R$)',
            'ticket_medio':'Ticket Médio','avaliacao':'Avaliação',
            'prazo_dias':'Prazo (dias)','pct_prazo':'% no Prazo'
        }),
        use_container_width=True, hide_index=True
    )

st.divider()
st.caption("Projeto acadêmico — FATEC Jundiaí | DW Olist | DuckDB + Streamlit")
