# -*- coding: utf-8 -*-
"""Sonda de fontes de dados.

Roda DENTRO do Render, que alcanca a internet livremente, e relata o que cada
fonte devolve. Serve para decidir a fonte definitiva com evidencia, em vez de
chute: o ambiente local do Claude nao alcanca stooq nem yahoo.
"""
import io
import json
import urllib.request
import urllib.error

import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 8


def _pegar(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read().decode("utf-8", "replace")


def testar_stooq():
    """Stooq serve CSV puro, sem chave nem crumb. Falta saber o sufixo da B3."""
    candidatos = [
        "petr4.sa", "petr4.br", "aapl.us",
    ]
    out = {}
    for s in candidatos:
        url = f"https://stooq.com/q/d/l/?s={s}&i=d"
        try:
            status, txt = _pegar(url)
            linhas = txt.strip().splitlines()
            out[s] = {
                "status": status,
                "linhas": len(linhas),
                "cabecalho": linhas[0][:80] if linhas else "",
                "ultima": linhas[-1][:80] if len(linhas) > 1 else "",
            }
        except Exception as e:
            out[s] = {"erro": f"{type(e).__name__}: {e}"[:120]}
    return out


def testar_yahoo():
    """Ate onde o Yahoo vai a partir deste IP, e com que data termina."""
    import yfinance as yf
    out = {}
    for s in ["BBAS3.SA", "PETR4.SA", "^BVSP", "AAPL", "BTC-USD"]:
        try:
            df = yf.download(s, period="1mo", interval="1d", auto_adjust=False,
                             progress=False, threads=False)
            if df is None or df.empty:
                out[s] = {"vazio": True}
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            out[s] = {
                "barras": int(len(df)),
                "ultima_data": str(df.index[-1].date()),
                "ultimo_fech": round(float(df["Close"].iloc[-1]), 4),
            }
        except Exception as e:
            out[s] = {"erro": f"{type(e).__name__}: {e}"[:160]}
    return out


def testar_coingecko():
    url = ("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
           "?vs_currency=usd&days=30&interval=daily")
    try:
        status, txt = _pegar(url)
        d = json.loads(txt)
        return {"status": status, "pontos": len(d.get("prices", []))}
    except Exception as e:
        return {"erro": f"{type(e).__name__}: {e}"[:160]}


def rodar_tudo():
    return {
        "stooq": testar_stooq(),
        "yahoo": testar_yahoo(),
        "coingecko": testar_coingecko(),
    }
