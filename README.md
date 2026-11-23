# Scanner diario — B3, EUA e cripto

Calcula todo dia os mesmos indicadores do painel "Medias Andre" do TradingView
e classifica cada ativo, para filtrar rapido onde vale olhar.

## O que ele calcula

Para cada ativo, no **diario** e no **semanal**:

| Indicador | Parametros |
|---|---|
| ATR | 14 (Wilder) + stop de 1,5 ATR |
| HiLo Activator | 5 — e o preco que faz virar na proxima barra |
| ADX | 14, 14 (Wilder) |
| IFR (RSI) | 9 |
| Forca relativa | 20 e 60 periodos |

Referencia da forca relativa: **IBOV** para B3, **S&P 500** para EUA, **BTC** para cripto.

Os indicadores foram conferidos contra a biblioteca `ta` e batem ate a sexta casa decimal.
As cotacoes sao baixadas **sem ajuste por dividendos** (`auto_adjust=False`), para os
numeros baterem com o Profit e com o TradingView.

## Classificacao

| Sinal | Criterio |
|---|---|
| **VIROU COMPRA** | HiLo diario virou comprador hoje, semanal comprador, ADX >= 20 |
| **COMPRA** | HiLo comprador nos dois tempos + as quatro forcas relativas positivas |
| **COMPRA FRACA** | HiLo comprador nos dois tempos, mas forca relativa fraca |
| **AGUARDAR** | Semanal comprador, diario ainda vendedor |
| **LATERAL** | ADX < 20 — sinal do HiLo nao vale |
| **VENDA** | HiLo vendedor nos dois tempos |

## Paginas

| Endereco | O que mostra |
|---|---|
| `/` | tabela com tudo, ordenada do melhor para o pior |
| `/?grupo=B3` | so B3 (tambem `EUA` e `CRIPTO`) |
| `/json` | os mesmos dados em JSON |
| `/?forcar=1` | recalcula na hora |
| `/ping` | acorda o servico |

## Como publicar no Render

1. Crie um repositorio no GitHub e suba estes 4 arquivos:
   `app.py`, `indicadores.py`, `tickers.py`, `requirements.txt`
2. No Render, crie um **Web Service** apontando para o repositorio:
   - Runtime: **Python**
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --timeout 300 --workers 1`
   - Plano: **Free**

## Sobre o plano gratuito

O servico dorme depois de 15 minutos sem uso. A primeira chamada do dia:

1. leva cerca de 50 segundos para acordar
2. devolve "Calculando..." e comeca a baixar as cotacoes em segundo plano
3. em cerca de 1 minuto a pagina ja mostra a tabela (ela recarrega sozinha)

Depois disso fica instantaneo por 6 horas.

## Para mudar os ativos

Edite **`tickers.py`**. Papeis da B3 vao sem o `.SA` (o programa acrescenta).
Cripto usa o formato `ZEC-USD`.
