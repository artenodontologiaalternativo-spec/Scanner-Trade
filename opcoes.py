# -*- coding: utf-8 -*-
"""Opcoes da B3: cadeia, volatilidade implicita, gregas e IV Rank.

De onde vem cada coisa:
  - precos, strikes e vencimentos: arquivo COTAHIST diario da B3 (publico)
  - volatilidade implicita e gregas: calculadas aqui, por Black-Scholes
  - IV Rank: compara a IV de hoje com a dos ultimos 12 meses, que estao
    no arquivo historico_iv.csv gravado junto com o codigo

O dado da B3 e de fechamento. Nao existe cotacao ao vivo aqui.
"""
import io
import json
import math
import os
import urllib.request
import zipfile
from datetime import date, datetime, timedelta

COTAHIST = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D%s.ZIP"
SELIC_API = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/"
             "ultimos/1?formato=json")
TAXA_RESERVA = 0.15  # usada so se o Banco Central nao responder

# sufixo do ativo conforme a especificacao do papel na B3
SUFIXO = {"ON": "3", "PN": "4", "PNA": "5", "PNB": "6", "PNC": "7",
          "PND": "8", "UNT": "11", "CI": "11", "DRN": "34"}

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_HISTORICO = os.path.join(BASE, "historico_iv.csv")

_cache = {"dia": None, "spots": None, "ops": None}
_historico = None
_taxa = {"valor": None, "quando": None}


# ------------------------------------------------------- Black-Scholes
def _norm(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _dens(x):
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def preco_bs(S, K, T, r, vol, tipo):
    """Preco teorico da opcao. tipo: 'C' para call, 'P' para put."""
    if T <= 0 or vol <= 0:
        return max(0.0, (S - K) if tipo == "C" else (K - S))
    d1 = (math.log(S / K) + (r + vol * vol / 2) * T) / (vol * math.sqrt(T))
    d2 = d1 - vol * math.sqrt(T)
    if tipo == "C":
        return S * _norm(d1) - K * math.exp(-r * T) * _norm(d2)
    return K * math.exp(-r * T) * _norm(-d2) - S * _norm(-d1)


def volatilidade_implicita(premio, S, K, T, r, tipo):
    """Acha a volatilidade que explica o premio negociado. None se impossivel."""
    piso = max(0.0, (S - K * math.exp(-r * T)) if tipo == "C"
               else (K * math.exp(-r * T) - S))
    if T <= 0 or premio <= piso + 1e-9:
        return None
    baixo, alto = 1e-4, 5.0
    if preco_bs(S, K, T, r, alto, tipo) < premio:
        return None
    for _ in range(60):
        meio = (baixo + alto) / 2
        if preco_bs(S, K, T, r, meio, tipo) < premio:
            baixo = meio
        else:
            alto = meio
    return (baixo + alto) / 2


def gregas(S, K, T, r, vol, tipo):
    """Delta, gamma, theta (por dia) e vega (por 1 ponto de vol)."""
    if T <= 0 or vol <= 0:
        return {}
    raiz = math.sqrt(T)
    d1 = (math.log(S / K) + (r + vol * vol / 2) * T) / (vol * raiz)
    d2 = d1 - vol * raiz
    desc = math.exp(-r * T)
    delta = _norm(d1) if tipo == "C" else _norm(d1) - 1
    theta_ano = (-S * _dens(d1) * vol / (2 * raiz)
                 - r * K * desc * (_norm(d2) if tipo == "C" else -_norm(-d2)))
    return {
        "delta": round(delta, 4),
        "gamma": round(_dens(d1) / (S * vol * raiz), 5),
        "theta": round(theta_ano / 365, 4),
        "vega": round(S * _dens(d1) * raiz / 100, 4),
    }


# ------------------------------------------------------------- taxa
def taxa_juros():
    """Selic meta ao ano, do Banco Central. Guarda por 12 horas."""
    agora = datetime.now()
    if _taxa["valor"] and _taxa["quando"] and \
            (agora - _taxa["quando"]) < timedelta(hours=12):
        return _taxa["valor"]
    try:
        req = urllib.request.Request(SELIC_API, headers={"Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=12) as r:
            dado = json.loads(r.read().decode("utf-8"))
        valor = float(str(dado[-1]["valor"]).replace(",", ".")) / 100
        if 0 < valor < 1:
            _taxa["valor"], _taxa["quando"] = valor, agora
            return valor
    except Exception:
        pass
    return _taxa["valor"] or TAXA_RESERVA


# --------------------------------------------------- arquivo da B3
def _baixar(dia):
    url = COTAHIST % dia.strftime("%d%m%Y")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()


def _ler(conteudo):
    """Decodifica o arquivo e separa acoes (spot) das opcoes."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    spots, ops = {}, {}
    with z.open(z.namelist()[0]) as f:
        for bruto in f:
            l = bruto.decode("latin-1")
            if not l.startswith("01"):
                continue
            merc = l[24:27]
            if merc == "010":
                ult = int(l[108:121]) / 100
                if ult > 0:
                    spots[l[12:24].strip()] = ult
                continue
            if merc not in ("070", "080"):
                continue
            esp = l[39:49].strip().split()
            suf = SUFIXO.get(esp[0]) if esp else None
            if not suf:
                continue
            venc = l[202:210]
            try:
                venc = date(int(venc[:4]), int(venc[4:6]), int(venc[6:8]))
            except ValueError:
                continue
            ops.setdefault(l[27:39].strip()[:4] + suf, []).append({
                "ticker": l[12:24].strip(),
                "tipo": "CALL" if merc == "070" else "PUT",
                "strike": int(l[188:201]) / 100,
                "vencimento": venc,
                "premio": int(l[108:121]) / 100,
                "abertura": int(l[56:69]) / 100,
                "maxima": int(l[69:82]) / 100,
                "minima": int(l[82:95]) / 100,
                "negocios": int(l[147:152]),
                "quantidade": int(l[152:170]),
                "volume": int(l[170:188]) / 100,
            })
    return spots, ops


def carregar_dia(dia=None):
    """Pega o arquivo do ultimo pregao. Volta ate 7 dias se nao achar."""
    if dia is None:
        dia = date.today()
    if _cache["dia"] == dia and _cache["spots"]:
        return _cache["dia"], _cache["spots"], _cache["ops"]
    erro = None
    for recuo in range(8):
        tentativa = dia - timedelta(days=recuo)
        if tentativa.weekday() >= 5:
            continue
        try:
            spots, ops = _ler(_baixar(tentativa))
            if spots:
                _cache.update({"dia": tentativa, "spots": spots, "ops": ops})
                return tentativa, spots, ops
        except Exception as e:
            erro = e
    raise RuntimeError("nao consegui baixar o arquivo da B3: %s" % erro)


# ------------------------------------------------------------ IV Rank
def historico():
    global _historico
    if _historico is None:
        _historico = {}
        try:
            with open(ARQ_HISTORICO, encoding="utf-8") as f:
                next(f)
                for linha in f:
                    p = linha.strip().split(";")
                    if len(p) >= 3:
                        _historico.setdefault(p[0], []).append(float(p[2]))
        except OSError:
            pass
    return _historico


def iv_rank(ativo, iv_hoje):
    """Onde a IV de hoje fica dentro da faixa dos ultimos 12 meses (0 a 100)."""
    serie = historico().get(ativo)
    if not serie or iv_hoje is None:
        return None, None, None
    menores = sum(1 for v in serie if v < iv_hoje)
    rank = 100.0 * menores / len(serie)
    return round(rank), round(min(serie) * 100, 1), round(max(serie) * 100, 1)


# ------------------------------------------------------------- cadeia
def cadeia(ativo, min_dias=20, max_dias=45, so_liquidas=True):
    """Monta a cadeia de opcoes do ativo com IV e gregas calculadas."""
    dia, spots, ops = carregar_dia()
    ativo = ativo.upper().strip()
    spot = spots.get(ativo)
    if spot is None:
        raise KeyError("ativo sem cotacao no arquivo do dia: %s" % ativo)
    r = taxa_juros()

    linhas = []
    for o in ops.get(ativo, []):
        dias = (o["vencimento"] - dia).days
        if dias < min_dias or dias > max_dias:
            continue
        if so_liquidas and o["negocios"] < 1:
            continue
        if o["strike"] <= 0 or o["premio"] <= 0:
            continue
        T = dias / 365.0
        tipo = "C" if o["tipo"] == "CALL" else "P"
        vol = volatilidade_implicita(o["premio"], spot, o["strike"], T, r, tipo)
        linha = dict(o)
        linha["vencimento"] = o["vencimento"].isoformat()
        linha["dias"] = dias
        linha["distancia_pct"] = round((o["strike"] / spot - 1) * 100, 2)
        linha["moneyness"] = _moneyness(o["tipo"], o["strike"], spot)
        linha["iv"] = round(vol * 100, 2) if vol else None
        linha.update({"delta": None, "gamma": None, "theta": None, "vega": None})
        if vol:
            linha.update(gregas(spot, o["strike"], T, r, vol, tipo))
        linhas.append(linha)

    linhas.sort(key=lambda x: (x["dias"], x["tipo"], x["strike"]))
    iv_atm = _iv_atm(linhas, spot)
    rank, menor, maior = iv_rank(ativo, iv_atm / 100 if iv_atm else None)
    return {
        "ativo": ativo,
        "data": dia.isoformat(),
        "preco": round(spot, 2),
        "taxa_juros_aa": round(r * 100, 2),
        "iv_atm": iv_atm,
        "iv_rank": rank,
        "iv_min_12m": menor,
        "iv_max_12m": maior,
        "leitura": _leitura(rank),
        "total": len(linhas),
        "opcoes": linhas,
    }


def _moneyness(tipo, strike, spot):
    dentro = strike < spot if tipo == "CALL" else strike > spot
    if abs(strike / spot - 1) < 0.01:
        return "ATM"
    return "ITM" if dentro else "OTM"


def _iv_atm(linhas, spot):
    """IV no dinheiro: mediana das opcoes mais coladas no preco do ativo."""
    perto = sorted((l for l in linhas if l["iv"]),
                   key=lambda l: abs(l["strike"] / spot - 1))[:6]
    vals = sorted(l["iv"] for l in perto)
    if not vals:
        return None
    m = len(vals)
    meio = vals[m // 2] if m % 2 else (vals[m // 2 - 1] + vals[m // 2]) / 2
    return round(meio, 2)


def _leitura(rank):
    """Regra do material: IV alta favorece venda, IV baixa favorece compra."""
    if rank is None:
        return "sem historico para comparar"
    if rank >= 80:
        return "IV alta (rank >= 80): ambiente de venda de opcoes"
    if rank <= 20:
        return "IV baixa (rank <= 20): ambiente de compra de opcoes"
    return "IV no meio da faixa: sem vantagem clara de vender ou comprar"
