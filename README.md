# 🛒 Data Warehouse — Brazilian E-Commerce Olist

**Projeto de Data Warehouse — FATEC Jundiaí | Banco de Dados / BI**

---

## Visão Geral

Construção de um Data Warehouse completo sobre o dataset público **Brazilian E-Commerce Olist** (Kaggle), com modelagem dimensional em esquema estrela, pipeline ETL em DuckDB/Python, 5 consultas analíticas e 4 visualizações interativas.

### Perguntas de Negócio Respondidas

1. Como evoluíram as vendas mês a mês ao longo de 2016–2018?
2. Quais são as 10 categorias de produto mais lucrativas?
3. Qual categoria vende mais em cada estado brasileiro?
4. Como cresce e como se comporta a retenção da base de clientes?
5. Quais estados têm maior ticket médio e melhor desempenho logístico?

---

## Pré-Requisitos

- Python 3.10+
- Bibliotecas: `duckdb`, `pandas`, `plotly`, `kaleido==0.2.1`

```bash
pip install duckdb pandas plotly kaleido==0.2.1
```

---

## Estrutura do Projeto

```
projeto-dw-olist/
├── README.md
├── olist_dw.duckdb              # Banco DuckDB gerado pelo pipeline
├── data/                        # CSVs do Olist (9 arquivos)
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
│   ├── 03_etl_load.sql          # Carga ETL (dim_date, SCD2, fact_sales)
│   ├── 04_analytics.sql         # 5 consultas analíticas
│   └── 05_performance.sql       # Tabela agregada + EXPLAIN
├── visualizacoes/
│   ├── gerar_graficos.py        # Script Python para gerar os gráficos
│   ├── grafico_1_evolucao_vendas.png
│   ├── grafico_2_top_categorias.png
│   ├── grafico_3_heatmap.png
│   └── grafico_4_dashboard.png
└── docs/
    ├── relatorio_tecnico.pdf
    ├── diagrama_modelo_estrela.png
    └── dicionario_dados.md
```

---

## Como Executar

### 1. Instalar dependências

```bash
pip install duckdb pandas plotly kaleido==0.2.1
```

### 2. Executar o pipeline ETL completo

```bash
python visualizacoes/gerar_graficos.py
```

Ou, passo a passo via DuckDB CLI:

```bash
duckdb olist_dw.duckdb < scripts/00_staging.sql
duckdb olist_dw.duckdb < scripts/01_oltp.sql
duckdb olist_dw.duckdb < scripts/02_dw_model.sql
duckdb olist_dw.duckdb < scripts/03_etl_load.sql
```

### 3. Executar análises

```bash
duckdb olist_dw.duckdb < scripts/04_analytics.sql
```

### 4. Gerar gráficos

```bash
python visualizacoes/gerar_graficos.py
```

---

## Modelo Dimensional (Esquema Estrela)

```
                    ┌─────────────┐
                    │  dim_date   │
                    │  date_key   │
                    └──────┬──────┘
                           │
┌──────────────┐    ┌──────▼──────┐    ┌─────────────┐
│ dim_customer │────│ fact_sales  │────│ dim_product │
│ customer_key │    │             │    │ product_key │
│ SCD Type 2   │    │ price       │    └─────────────┘
└──────────────┘    │ freight     │
                    │ review_score│    ┌─────────────┐
                    │ days_delay  │────│ dim_seller  │
                    └─────────────┘    │ seller_key  │
                                       └─────────────┘
```

**Grain**: 1 linha por item de pedido  
**SCD Type 2**: dim_customer rastreia mudanças de localização  

---

## Métricas Finais

| Indicador | Valor |
|-----------|-------|
| Total de itens (fato) | 112.650 |
| Pedidos únicos | 98.199 |
| Clientes únicos | 96.096 |
| Receita total | R$ 15.735.527 |
| Avaliação média | 4,04 / 5,00 |
| Período dos dados | Set/2016 – Out/2018 |

---

## Dataset

- **Fonte**: [Kaggle — Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- **Tamanho**: ~45 MB (9 arquivos CSV)
- **Licença**: CC BY-NC-SA 4.0
