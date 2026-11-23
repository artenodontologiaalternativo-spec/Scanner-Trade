# -*- coding: utf-8 -*-
"""Listas de ativos do scanner. Edite aqui para incluir ou remover papeis."""

# --------- B3 (sufixo .SA no Yahoo) ---------
B3 = [
    # universo acompanhado
    "BBAS3", "ITUB4", "VALE3", "WEGE3", "CMIG4", "PETR4", "BBDC4", "SUZB3",
    # analisados recentemente
    "BBSE3", "LREN3", "MGLU3", "EGIE3", "SANB11", "BRSR6", "B3SA3",
    # demais liquidas
    "ABEV3", "PRIO3", "RENT3", "EQTL3", "RADL3", "RAIL3", "ELET3", "GGBR4",
    "GOAU4", "CSNA3", "USIM5", "KLBN11", "CPLE6", "SBSP3", "TOTS3", "HYPE3",
    "VIVT3", "CYRE3", "EMBJ3", "SLCE3", "CPFE3", "TIMS3", "ASAI3", "NTCO3",
    # ETFs
    "BOVA11", "GOLD11", "IVVB11", "SMAL11",
]
B3_REF = "^BVSP"          # Ibovespa
B3_REF_NOME = "IBOV"

# --------- EUA ---------
EUA = [
    "IGV", "GILD", "SCHW", "RIOT", "GLD", "AMAT", "EFA", "TEM", "JMIA", "XLF",
    "UUUU", "CSCO", "HYG", "SLV", "GM", "SONY", "OKLO", "NLY", "UBER", "HUT",
    "ABBV", "PATH", "IBIT", "SHOP", "NBIS", "CCJ", "WULF", "ROIV", "AZN", "WFC",
    "EEM", "VICI", "HBM", "TSM", "APLD", "QBTS", "ANET", "D", "PEP", "APH",
    "RGTI", "VWO", "RKLB", "PPL", "URA", "VLY", "CDE", "JPM", "VRT", "CLSK",
    "EXC", "SILJ", "MU", "GLW", "CNP", "KR", "AAPL", "HOOD", "SBSW", "CORZ",
    "IREN", "FHN", "VST", "PL", "AEP", "EQX", "KO", "EOSE", "ARKK", "HPE",
    "VALE", "BTU", "DELL", "NEE", "BP", "RUN", "CLF", "CVS", "ABT", "GDXJ",
    "PLTR", "EWJ", "AMD", "CPNG", "C", "PAAS", "GOOGL", "MP", "KGC", "CIFR",
    "UEC", "LQD", "ASTS", "SNOW", "XLP", "MSFT", "HL", "EWZ", "AG", "QS",
    "BE", "ETSY", "NEM", "CSX", "QQQ", "BAC", "GDX", "INTC", "BANC", "XLV",
    "JNJ", "FXI", "SMH", "RSP", "NVDA", "AVGO",
]
EUA_REF = "^GSPC"         # S&P 500
EUA_REF_NOME = "SPX"

# --------- Cripto (principais) ---------
CRIPTO = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
    "ZEC-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "DOGE-USD",
    "LTC-USD", "DOT-USD",
]
CRIPTO_REF = "BTC-USD"    # alts sao comparadas ao bitcoin
CRIPTO_REF_NOME = "BTC"
