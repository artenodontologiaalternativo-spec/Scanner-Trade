# -*- coding: utf-8 -*-
"""Indicadores identicos aos do indicador 'Medias Andre' do TradingView.

Importante: ATR, IFR e ADX usam a suavizacao de Wilder (RMA), igual ao Pine
(ta.atr, ta.rsi, ta.dmi). Usar EMA comum daria numeros diferentes.
"""
import numpy as np
import pandas as pd


def rma(serie: pd.Series, n: int) -> pd.Series:
    """Media movel de Wilder, equivalente ao ta.rma do Pine."""
    return serie.ewm(alpha=1.0 / n, adjust=False).mean()


def true_range(h, l, c):
    fecha_ant = c.shift(1)
    return pd.concat([h - l, (h - fecha_ant).abs(), (l - fecha_ant).abs()], axis=1).max(axis=1)


def atr(h, l, c, n=14):
    return rma(true_range(h, l, c), n)


def ifr(c, n=9):
    delta = c.diff()
    ganho = rma(delta.clip(lower=0), n)
    perda = rma((-delta).clip(lower=0), n)
    rs = ganho / perda.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100 * (ganho > 0))


def adx(h, l, c, n=14, m=14):
    """ADX de Wilder. n = periodo do direcional, m = media do ADX."""
    sobe = h.diff()
    desce = -l.diff()
    mais_dm = pd.Series(np.where((sobe > desce) & (sobe > 0), sobe, 0.0), index=h.index)
    menos_dm = pd.Series(np.where((desce > sobe) & (desce > 0), desce, 0.0), index=h.index)
    tr_s = rma(true_range(h, l, c), n).replace(0, np.nan)
    mais_di = 100 * rma(mais_dm, n) / tr_s
    menos_di = 100 * rma(menos_dm, n) / tr_s
    soma = (mais_di + menos_di).replace(0, np.nan)
    dx = 100 * (mais_di - menos_di).abs() / soma
    return rma(dx.fillna(0), m)


def hilo(h, l, c, n=5):
    """HiLo Activator. Devolve (tendencia, linha, gatilho).

    tendencia: 1 comprador, -1 vendedor
    linha:     valor plotado no grafico
    gatilho:   preco que, se o fechamento superar/perder, vira na proxima barra
    """
    media_max = h.rolling(n).mean()
    media_min = l.rolling(n).mean()
    mx = media_max.shift(1).to_numpy()
    mn = media_min.shift(1).to_numpy()
    fecha = c.to_numpy()

    tend = np.ones(len(c), dtype=int)
    atual = 1
    for i in range(len(c)):
        if not np.isnan(mx[i]) and fecha[i] > mx[i]:
            atual = 1
        elif not np.isnan(mn[i]) and fecha[i] < mn[i]:
            atual = -1
        tend[i] = atual

    tend = pd.Series(tend, index=c.index)
    linha = pd.Series(np.where(tend == 1, mn, mx), index=c.index)
    gatilho = pd.Series(np.where(tend == 1, media_min, media_max), index=c.index)
    return tend, linha, gatilho


def forca_relativa(c, c_ref, n):
    """Quanto o ativo rendeu a mais (ou a menos) que a referencia, em p.p."""
    a = (c / c.shift(n) - 1) * 100
    b = (c_ref / c_ref.shift(n) - 1) * 100
    return a - b


def para_semanal(df: pd.DataFrame) -> pd.DataFrame:
    """Reamostra OHLC diario para semanal (semana fechando na sexta)."""
    regra = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    cols = {k: v for k, v in regra.items() if k in df.columns}
    return df.resample("W-FRI").agg(cols).dropna(how="all")
