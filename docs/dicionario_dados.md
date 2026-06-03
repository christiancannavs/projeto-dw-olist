# Dicionário de Dados — Data Warehouse Olist

## Camada: Data Warehouse (Esquema Estrela)

---

### dim_date — Dimensão de Data

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| date_key | INTEGER | Chave surrogate (YYYYMMDD) | 20171125 |
| full_date | DATE | Data completa | 2017-11-25 |
| year | INTEGER | Ano | 2017 |
| quarter | INTEGER | Trimestre (1–4) | 4 |
| month | INTEGER | Mês (1–12) | 11 |
| month_name | VARCHAR | Nome do mês em inglês | November |
| week_of_year | INTEGER | Semana do ano (1–53) | 47 |
| day_of_month | INTEGER | Dia do mês (1–31) | 25 |
| day_of_week | INTEGER | Dia da semana (1=Dom…7=Sáb) | 7 |
| day_name | VARCHAR | Nome do dia da semana | Saturday |
| is_weekend | BOOLEAN | Indica final de semana | TRUE |
| is_holiday | BOOLEAN | Indica feriado (placeholder) | FALSE |

---

### dim_customer — Dimensão de Cliente (SCD Type 2)

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| customer_key | INTEGER | Chave surrogate (PK) | 1 |
| customer_unique_id | VARCHAR(50) | ID único do cliente (chave de negócio) | 861eff4711... |
| customer_city | VARCHAR(100) | Cidade do cliente | SAO PAULO |
| customer_state | CHAR(2) | Estado (UF) | SP |
| customer_zip_code | VARCHAR(10) | CEP (5 dígitos) | 01310 |
| scd_start_date | DATE | Data de início da validade do registro | 2017-01-15 |
| scd_end_date | DATE | Data de fim (NULL = registro atual) | NULL |
| scd_is_current | BOOLEAN | Indica se é o registro vigente | TRUE |

> **SCD Type 2**: quando o cliente muda de cidade/estado, o registro antigo recebe `scd_end_date` e `scd_is_current = FALSE`, e um novo registro é criado.

---

### dim_product — Dimensão de Produto

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| product_key | INTEGER | Chave surrogate (PK) | 412 |
| product_id | VARCHAR(50) | ID do produto (chave de negócio) | 1e9e8ef04d... |
| product_category | VARCHAR(100) | Categoria em inglês | health_beauty |
| product_weight_g | INTEGER | Peso em gramas | 350 |
| product_length_cm | INTEGER | Comprimento em cm | 20 |
| product_height_cm | INTEGER | Altura em cm | 10 |
| product_width_cm | INTEGER | Largura em cm | 15 |
| product_volume_cm3 | INTEGER | Volume calculado (L×A×C) | 3000 |

---

### dim_seller — Dimensão de Vendedor

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| seller_key | INTEGER | Chave surrogate (PK) | 87 |
| seller_id | VARCHAR(50) | ID do vendedor (chave de negócio) | 3442f895... |
| seller_city | VARCHAR(100) | Cidade do vendedor | CAMPINAS |
| seller_state | CHAR(2) | Estado (UF) | SP |
| seller_zip_code | VARCHAR(10) | CEP (5 dígitos) | 13023 |

---

### fact_sales — Tabela Fato de Vendas

**Grain**: 1 linha por item de pedido (combinação única de `order_id` + `order_item_id`)

| Coluna | Tipo | Descrição | Exemplo |
|--------|------|-----------|---------|
| date_key | INTEGER | FK → dim_date | 20171125 |
| customer_key | INTEGER | FK → dim_customer | 1024 |
| product_key | INTEGER | FK → dim_product | 412 |
| seller_key | INTEGER | FK → dim_seller | 87 |
| order_id | VARCHAR(50) | ID do pedido (negócio) | e481f51cbd... |
| order_item_id | INTEGER | Nº do item no pedido | 1 |
| price | DECIMAL(10,2) | Preço do produto (R$) | 149.90 |
| freight_value | DECIMAL(10,2) | Valor do frete (R$) | 18.50 |
| total_revenue | DECIMAL(10,2) | Preço + frete (R$) | 168.40 |
| payment_value | DECIMAL(10,2) | Valor total pago pelo cliente (R$) | 168.40 |
| payment_type | VARCHAR(30) | Forma de pagamento | credit_card |
| review_score | INTEGER | Avaliação do cliente (1–5; NULL se não avaliou) | 4 |
| order_status | VARCHAR(20) | Status do pedido | delivered |
| days_to_delivery | INTEGER | Dias da compra até entrega real (NULL se não entregue) | 8 |
| days_estimated | INTEGER | Dias da compra até entrega estimada | 14 |
| delivery_delay | INTEGER | Atraso em dias (negativo = adiantado) | -6 |

---

## Camada: OLTP (Normalização)

| Tabela | Descrição | Linhas aprox. |
|--------|-----------|---------------|
| oltp_orders | Pedidos limpos com timestamps | 99.441 |
| oltp_order_items | Itens dos pedidos | 112.650 |
| oltp_customers | Clientes únicos (por customer_unique_id) | 96.096 |
| oltp_products | Produtos com categoria traduzida | 32.951 |
| oltp_sellers | Vendedores únicos | 3.095 |
| oltp_order_payments | Pagamento principal por pedido | 99.440 |
| oltp_order_reviews | Avaliação mais recente por pedido | 99.143 |

---

## Métricas do DW (após ETL completo)

| Indicador | Valor |
|-----------|-------|
| Total de itens na fact_sales | 112.650 |
| Pedidos únicos carregados | 98.199 |
| Clientes únicos | 96.096 |
| Produtos únicos | 32.951 |
| Vendedores únicos | 3.095 |
| Período coberto | Set/2016 – Out/2018 |
| Receita total (entregues) | R$ 15.735.527,03 |
| Avaliação média | 4,04 / 5,00 |
