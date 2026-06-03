# 🛒 Data Warehouse — Brazilian E-Commerce Olist

**Projeto de Data Warehouse — FATEC Jundiaí | Banco de Dados / BI | 2025**

---

## Visão Geral

Construção de um Data Warehouse completo sobre o dataset público **Brazilian E-Commerce Olist** (Kaggle), com modelagem dimensional em esquema estrela, pipeline ETL em DuckDB/Python, 5 consultas analíticas, 4 visualizações e dashboard interativo publicado.

### Perguntas de Negócio Respondidas

1. Como evoluíram as vendas mês a mês ao longo de 2016–2018?
2. Quais são as 10 categorias de produto mais lucrativas?
3. Qual categoria vende mais em cada estado brasileiro?
4. Como cresce e como se comporta a retenção da base de clientes?
5. Quais estados têm maior ticket médio e melhor desempenho logístico?

---

## Resultados do Projeto

| Indicador | Valor |
|-----------|-------|
| Total de itens na fact_sales | 112.650 |
| Pedidos únicos | 98.199 |
| Clientes únicos | 96.096 |
| Produtos únicos | 32.951 |
| Vendedores únicos | 3.095 |
| Período coberto | Set/2016 – Out/2018 |
| Receita total (entregues) | R$ 13.494.401 |
| Avaliação média | 4,04 / 5,00 |

---

## Pré-Requisitos

- Python 3.10+
- Pacotes: `duckdb pandas plotly kaleido==0.2.1 streamlit`

```bash
pip install duckdb pandas plotly kaleido==0.2.1 streamlit
```

---

## Estrutura do Projeto

```
projeto-dw-olist/
├── README.md
├── setup_dw.py                  # Script principal: cria o banco do zero
├── olist_dw.duckdb              # Banco DuckDB (gerado pelo setup_dw.py)
├── dashboard_streamlit.py       # Dashboard interativo (Streamlit)
├── requirements.txt             # Dependências para deploy no Streamlit Cloud
├── data/                        # 9 CSVs do Olist
│   ├── olist_orders_dataset.csv
│   ├── olist_order_items_dataset.csv
│   ├── olist_customers_dataset.csv
│   ├── olist_products_dataset.csv
│   ├── olist_sellers_dataset.csv
│   ├── olist_order_payments_dataset.csv
│   ├── olist_order_reviews_dataset.csv
│   ├── olist_geolocation_dataset.csv
│   └── product_category_name_translation.csv
├── scripts/
│   ├── 00_staging.sql           # Views sobre os CSVs brutos
│   ├── 01_oltp.sql              # Normalização e limpeza
│   ├── 02_dw_model.sql          # DDL das dimensões e fato
│   ├── 03_etl_load.sql          # Carga ETL (SCD2, dim_date, fact_sales)
│   ├── 04_analytics.sql         # 5 consultas analíticas
│   └── 05_performance.sql       # Tabela agregada + EXPLAIN ANALYZE
├── visualizacoes/
│   ├── gerar_graficos.py        # Gera os 4 gráficos PNG
│   ├── grafico_1_evolucao_vendas.png
│   ├── grafico_2_top_categorias.png
│   ├── grafico_3_heatmap.png
│   └── grafico_4_dashboard.png
├── tests/
│   └── test_dw.py               # 13 testes automatizados de integridade
├── bonus/
│   ├── postgres_etl.py          # ETL para PostgreSQL + comparação de performance
└── docs/
    ├── relatorio_tecnico.pdf
    ├── relatorio_tecnico.docx
    └── dicionario_dados.md
```

---

## Como Executar

### 1. Instalar dependências

```bash
pip install duckdb pandas plotly kaleido==0.2.1 streamlit psycopg2-binary
```

### 2. Criar o banco DuckDB (pipeline ETL completo)

```bash
python setup_dw.py
```

Saída esperada: todas as tabelas carregadas com contagem de linhas e `"Banco criado com sucesso!"`.  
Tempo estimado: ~2–3 minutos.

### 3. Gerar os gráficos

```bash
python visualizacoes/gerar_graficos.py
```

Gera 4 arquivos PNG na pasta `visualizacoes/`.

### 4. Rodar os testes de integridade

```bash
python tests/test_dw.py
```

Saída esperada: `13/13 testes passaram — TODOS OK`.

### 5. Rodar o dashboard interativo

```bash
streamlit run dashboard_streamlit.py
```

Abre automaticamente em `http://localhost:8501`.

---

## Dashboard Interativo (publicado)

Acesse o dashboard online — sem precisar instalar nada:

🔗 **[projeto-dw-olist.streamlit.app](https://projeto-dw-olist.streamlit.app)**

Funcionalidades:
- Filtros por ano, categoria e estado (sidebar)
- Gráfico de linha interativo com alternância entre receita, pedidos e avaliação
- Ranking de categorias com slider e ordenação configurável
- Gráfico de pizza de formas de pagamento
- Distribuição de avaliações
- Tabela e gráfico de KPIs por estado com 4 ordenações

---

## Modelo Dimensional (Esquema Estrela)

```
                   ┌─────────────┐
                   │  dim_date   │
                   │  date_key   │
                   └──────┬──────┘
                          │
┌──────────────┐   ┌──────▼──────┐   ┌─────────────┐
│ dim_customer │───│ fact_sales  │───│ dim_product │
│  SCD Type 2  │   │             │   └─────────────┘
└──────────────┘   │ price       │
                   │ freight     │   ┌─────────────┐
                   │ review_score│───│ dim_seller  │
                   │ delivery_   │   └─────────────┘
                   │   delay     │
                   └─────────────┘
```

**Grain:** 1 linha por item de pedido  
**SCD Type 2:** `dim_customer` rastreia mudanças históricas de localização

---

## Bônus Implementados

### ✅ Dashboard interativo — Streamlit Cloud (+5%)
Dashboard publicado com filtros, gráficos interativos e tabelas ordenáveis.  
Deploy gratuito via [Streamlit Cloud](https://streamlit.io/cloud).

### ✅ Testes automatizados (+5%)
13 testes de integridade em `tests/test_dw.py` cobrindo:
- Contagem mínima de linhas em todas as tabelas
- Unicidade de chaves primárias
- Integridade referencial (FK → PK)
- Ausência de NULLs em campos obrigatórios
- Validação de valores (preços negativos, notas fora do range)
- Consistência do SCD Type 2
- Sanidade das métricas de negócio (receita, ticket médio, avaliação)

### ✅ PostgreSQL + DuckDB — comparação (+5%)
Script `bonus/postgres_etl.py` que:
- Cria a mesma estrutura de DW no PostgreSQL 18
- Carrega todas as tabelas via `psycopg2`
- Cria índices otimizados
- Executa a mesma query analítica nos dois bancos e compara o tempo

Resultado típico: **DuckDB ~10–30x mais rápido** para queries OLAP, confirmando que bancos colunares são superiores para analytics enquanto o PostgreSQL é ideal para OLTP.


---

## Pipeline ETL — Detalhes

| Script | Camada | O que faz |
|--------|--------|-----------|
| `00_staging.sql` | Staging | Views sobre os 9 CSVs sem transformação |
| `01_oltp.sql` | OLTP | Normalização, deduplicação, tratamento de NULLs |
| `02_dw_model.sql` | DW | DDL das 4 dimensões e fact_sales |
| `03_etl_load.sql` | ETL | Carga completa com SCD Type 2 |
| `04_analytics.sql` | Analytics | 5 queries de negócio |
| `05_performance.sql` | Performance | Tabela agregada + EXPLAIN ANALYZE |

**Todos os scripts são idempotentes** — podem ser reexecutados sem duplicar dados.

---

## Dataset

- **Fonte:** [Kaggle — Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- **Tamanho:** ~45 MB (9 arquivos CSV)
- **Licença:** CC BY-NC-SA 4.0
- **Período:** Setembro/2016 – Outubro/2018

---

## Tecnologias Utilizadas

| Tecnologia | Uso |
|------------|-----|
| DuckDB 1.5.3 | Banco principal (OLAP) |
| PostgreSQL 18 | Bônus: comparação de performance |
| Python 3.13 | ETL, gráficos, testes |
| Streamlit | Dashboard interativo |
| Plotly | Visualizações |
| pandas / numpy | Manipulação de dados |
