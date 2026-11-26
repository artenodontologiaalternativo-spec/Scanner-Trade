# -*- coding: utf-8 -*-
"""Scanner diario — B3, EUA e cripto.

Calcula os mesmos indicadores do painel 'Medias Andre' (ATR, HiLo, ADX,
IFR 9 e forca relativa) no diario e no semanal, e classifica cada ativo.

Endpoints:
  /        tabela em HTML
  /json    mesmos dados em JSON
  /ping    acorda o servico
"""
import os
import threading
import time
import traceback
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, request

import diagnostico as diag
import indicadores as ind
import tickers as tk

app = Flask(__name__)

VALIDADE_HORAS = 6
CACHE = {"dados": None, "quando": None, "rodando": False, "erro": None}
FUSO = timezone(timedelta(hours=-3))  # horario de Brasilia


# ----------------------------------------------------------------- coleta
def baixar(simbolos, periodo="2y"):
    """Baixa OHLC diario. auto_adjust=False para bater com o Profit/TradingView."""
    dados = yf.download(
        simbolos, period=periodo, interval="1d",
        auto_adjust=False, progress=False, group_by="ticker", threads=True,
    )
    saida = {}
    for s in simbolos:
        try:
            df = dados[s] if isinstance(dados.columns, pd.MultiIndex) else dados
            df = df.dropna(subset=["Close"])
            if len(df) >= 210:
                saida[s] = df
        except Exception:
            continue
    return saida


# ------------------------------------------------------------- calculo
def medir(df, df_ref):
    """Calcula o painel para um ativo, no diario e no semanal."""
    h, l, c = df["High"], df["Low"], df["Close"]
    r = {}

    r["preco"] = float(c.iloc[-1])
    r["data"] = str(c.index[-1].date())  # data do candle usado
    r["var_dia"] = float((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) > 1 else 0.0

    a = ind.atr(h, l, c, 14)
    r["atr"] = float(a.iloc[-1])
    r["atr_pct"] = float(a.iloc[-1] / c.iloc[-1] * 100)
    r["stop"] = round(float(a.iloc[-1]) * 1.5, 2)
    r["ifr"] = float(ind.ifr(c, 9).iloc[-1])
    r["adx"] = float(ind.adx(h, l, c, 14, 14).iloc[-1])

    t, _, gat = ind.hilo(h, l, c, 5)
    r["hilo_d"] = "Comprador" if t.iloc[-1] == 1 else "Vendedor"
    r["gatilho"] = round(float(gat.iloc[-1]), 2)
    r["virou_hoje"] = bool(len(t) > 1 and t.iloc[-1] != t.iloc[-2])

    # medias
    r["acima_ema20"] = bool(c.iloc[-1] > c.ewm(span=20, adjust=False).mean().iloc[-1])
    r["acima_ma200"] = bool(len(c) >= 200 and c.iloc[-1] > c.rolling(200).mean().iloc[-1])

    # forca relativa diaria
    ref = df_ref["Close"].reindex(c.index).ffill()
    r["fr20d"] = float(ind.forca_relativa(c, ref, 20).iloc[-1])
    r["fr60d"] = float(ind.forca_relativa(c, ref, 60).iloc[-1])

    # semanal
    sem = ind.para_semanal(df)
    sem_ref = ind.para_semanal(df_ref)
    hs, ls, cs = sem["High"], sem["Low"], sem["Close"]
    ts, _, _ = ind.hilo(hs, ls, cs, 5)
    r["hilo_s"] = "Comprador" if ts.iloc[-1] == 1 else "Vendedor"
    r["adx_s"] = float(ind.adx(hs, ls, cs, 14, 14).iloc[-1])
    r["atr_s_pct"] = float(ind.atr(hs, ls, cs, 14).iloc[-1] / cs.iloc[-1] * 100)
    refs = sem_ref["Close"].reindex(cs.index).ffill()
    r["fr20s"] = float(ind.forca_relativa(cs, refs, 20).iloc[-1])
    r["fr60s"] = float(ind.forca_relativa(cs, refs, 60).iloc[-1])
    return r


def classificar(r):
    """Aplica as regras do metodo e devolve (sinal, nota para ordenacao)."""
    d_comp = r["hilo_d"] == "Comprador"
    s_comp = r["hilo_s"] == "Comprador"
    tend = r["adx"] >= 20
    fr_ok = r["fr20d"] > 0 and r["fr60d"] > 0 and r["fr20s"] > 0 and r["fr60s"] > 0

    if not tend:
        return "LATERAL", 10 + r["adx"]
    if r["virou_hoje"] and d_comp and s_comp:
        return "VIROU COMPRA", 900 + r["adx"]
    if d_comp and s_comp and fr_ok:
        return "COMPRA", 800 + (r["fr20d"] + r["fr60d"]) / 2
    if d_comp and s_comp:
        return "COMPRA FRACA", 600 + (r["fr20d"] + r["fr60d"]) / 2
    if s_comp and not d_comp:
        return "AGUARDAR", 400 + r["fr60s"]
    if r["virou_hoje"] and not d_comp:
        return "VIROU VENDA", 200
    return "VENDA", 100 + r["fr60s"]


def rodar():
    """Baixa tudo e monta a lista final. Roda em thread separada."""
    linhas = []
    grupos = [
        ("B3", tk.B3, ".SA", tk.B3_REF, tk.B3_REF_NOME),
        ("EUA", tk.EUA, "", tk.EUA_REF, tk.EUA_REF_NOME),
        ("CRIPTO", tk.CRIPTO, "", tk.CRIPTO_REF, tk.CRIPTO_REF_NOME),
    ]
    for grupo, lista, sufixo, ref_sym, ref_nome in grupos:
        simbolos = [t + sufixo for t in lista]
        baixados = baixar(list(dict.fromkeys(simbolos + [ref_sym])))
        if ref_sym not in baixados:
            continue
        df_ref = baixados[ref_sym]
        for nome, sym in zip(lista, simbolos):
            if sym not in baixados:
                continue
            try:
                r = medir(baixados[sym], df_ref)
            except Exception:
                continue
            r["ativo"] = nome
            r["grupo"] = grupo
            r["referencia"] = ref_nome
            r["sinal"], r["nota"] = classificar(r)
            r["tradingview"] = link_tv(nome, grupo)
            linhas.append(r)
    linhas.sort(key=lambda x: -x["nota"])
    return linhas


def atualizar():
    CACHE["rodando"] = True
    CACHE["erro"] = None
    try:
        CACHE["dados"] = rodar()
        CACHE["quando"] = datetime.now(FUSO)
        _registrar_resumo(CACHE["dados"])
    except Exception:
        CACHE["erro"] = traceback.format_exc()[-800:]
        print("RESUMO_ERRO " + CACHE["erro"][-400:].replace("\n", " | "), flush=True)
    finally:
        CACHE["rodando"] = False


def _registrar_resumo(linhas):
    """Escreve no log do servidor a data do dado e as viradas.

    O log e o unico canal que sempre funciona: o WebFetch do Claude falha na
    checagem de robots enquanto o servico do plano gratuito acorda, e isso
    derruba tanto a leitura manual quanto a tarefa diaria.
    """
    import json as _json
    resumo = datas_do_dado(linhas)
    print("RESUMO datas " + _json.dumps(resumo, default=str), flush=True)
    viradas = [f'{d["ativo"]}:{d["sinal"].split()[-1]}:{d["preco"]:.2f}:{d["data"]}'
               for d in linhas if d["sinal"].startswith("VIROU")]
    print(f"RESUMO total={len(linhas)} viradas={len(viradas)} " +
          " ".join(viradas[:40]), flush=True)
    for g in ("BBAS3", "PETR4", "VALE3", "AAPL", "BTC-USD"):
        for d in linhas:
            if d["ativo"] == g:
                print(f'RESUMO amostra {g} preco={d["preco"]:.2f} '
                      f'var={d["var_dia"]:+.2f}% data={d["data"]}', flush=True)
                break


def fresco():
    if not CACHE["dados"] or not CACHE["quando"]:
        return False
    return (datetime.now(FUSO) - CACHE["quando"]) < timedelta(hours=VALIDADE_HORAS)


def garantir(forcar=False):
    """Devolve True se ha dados prontos; senao dispara o calculo em segundo plano."""
    if fresco() and not forcar:
        return True
    if not CACHE["rodando"]:
        threading.Thread(target=atualizar, daemon=True).start()
    return False


# ------------------------------------------------------------ tradingview
# Sem ID de layout: o link abre no grafico padrao do usuario logado,
# que ja carrega os indicadores dele. Com ID, o TradingView recusa o acesso.


def link_tv(ativo, grupo):
    if grupo == "B3":
        simbolo = "BMFBOVESPA:" + ativo
    elif grupo == "CRIPTO":
        simbolo = "CRYPTO:" + ativo.replace("-USD", "") + "USD"
    else:
        simbolo = ativo
    return f"https://br.tradingview.com/chart/?symbol={simbolo.replace(':', '%3A')}"


# ----------------------------------------------------------------- saida
COR = {
    "VIROU COMPRA": "#3b82f6", "COMPRA": "#22c55e", "COMPRA FRACA": "#84cc16",
    "AGUARDAR": "#eab308", "LATERAL": "#9ca3af", "VIROU VENDA": "#f97316",
    "VENDA": "#ef4444",
}


def cel(v, casas=1, pct=True):
    cor = "#22c55e" if v >= 0 else "#ef4444"
    return f'<td style="color:{cor}">{v:+.{casas}f}{"%" if pct else ""}</td>'


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /\n", 200, {"Content-Type": "text/plain"}


@app.route("/ping")
def ping():
    garantir()
    return jsonify(pronto=fresco(), rodando=CACHE["rodando"],
                   quando=CACHE["quando"].isoformat() if CACHE["quando"] else None)


def datas_do_dado(linhas):
    """Resume a data do ultimo candle por grupo.

    O relogio do servidor nao diz nada sobre a idade do DADO: a fonte pode
    entregar um candle de dias atras e o calculo roda normalmente. Esta funcao
    expoe isso, para o scanner nunca mais publicar dado velho como se fosse de
    hoje.
    """
    por_grupo = {}
    for d in linhas:
        g = d.get("grupo", "?")
        dt = d.get("data")
        if dt:
            por_grupo.setdefault(g, {}).setdefault(dt, 0)
            por_grupo[g][dt] += 1
    resumo = {}
    for g, contagem in por_grupo.items():
        mais_comum = max(contagem.items(), key=lambda kv: kv[1])[0]
        resumo[g] = {"data": mais_comum, "ativos": contagem[mais_comum],
                     "divergentes": sum(v for k, v in contagem.items() if k != mais_comum)}
    return resumo


@app.route("/diagnostico")
def rota_diagnostico():
    """Sonda as fontes de dados de dentro do Render. So para depuracao."""
    return jsonify(diag.rodar_tudo())


@app.route("/json")
def rota_json():
    if not garantir(request.args.get("forcar") == "1"):
        return jsonify(status="calculando",
                       aviso="Aguarde cerca de 60 segundos e chame de novo.",
                       erro=CACHE["erro"]), 202
    return jsonify(status="ok",
                   calculado_em=CACHE["quando"].strftime("%d/%m/%Y %H:%M"),
                   data_do_dado=datas_do_dado(CACHE["dados"]),
                   total=len(CACHE["dados"]), ativos=CACHE["dados"])


@app.route("/")
def home():
    grupo = request.args.get("grupo", "").upper()
    if not garantir(request.args.get("forcar") == "1"):
        aviso = "<p>Erro na ultima tentativa.</p>" if CACHE["erro"] else ""
        return f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=20>
<body style="background:#0b0b0f;color:#eee;font-family:system-ui;padding:40px">
<h2>Calculando...</h2><p>Baixando cotacoes e calculando indicadores.
A pagina recarrega sozinha a cada 20 segundos.</p>{aviso}</body>""", 202

    dados = [d for d in CACHE["dados"] if not grupo or d["grupo"] == grupo]
    linhas = []
    for d in dados:
        linhas.append(
            f'<tr><td><a href="{d["tradingview"]}" target=_blank><b>{d["ativo"]}</b></a></td><td class=g>{d["grupo"]}</td>'
            f'<td style="background:{COR[d["sinal"]]}22;color:{COR[d["sinal"]]};font-weight:600">{d["sinal"]}</td>'
            f'<td>{d["preco"]:.2f}</td>' + cel(d["var_dia"]) +
            f'<td>{d["atr_pct"]:.1f}%</td><td>{d["stop"]:.2f}</td>'
            f'<td>{d["ifr"]:.0f}</td>'
            f'<td style="color:{"#22c55e" if d["adx"]>=25 else "#eab308" if d["adx"]>=20 else "#9ca3af"}">{d["adx"]:.0f}</td>'
            + cel(d["fr20d"]) + cel(d["fr60d"]) + cel(d["fr20s"]) + cel(d["fr60s"]) +
            f'<td style="color:{"#22c55e" if d["hilo_d"]=="Comprador" else "#ef4444"}">{d["hilo_d"][:4]}</td>'
            f'<td style="color:{"#22c55e" if d["hilo_s"]=="Comprador" else "#ef4444"}">{d["hilo_s"][:4]}</td>'
            f'<td>{d["gatilho"]:.2f}</td></tr>'
        )
    resumo = datas_do_dado(dados)
    partes = []
    for g, info in sorted(resumo.items()):
        extra = f' (+{info["divergentes"]} fora)' if info["divergentes"] else ""
        partes.append(f'{g}: {info["data"]}{extra}')
    selo_data = "Ultimo candle — " + " · ".join(partes) if partes else "sem dados"

    cab = ("Ativo|Grupo|Sinal|Preco|Dia|ATR%|Stop|IFR|ADX|"
           "FR20d|FR60d|FR20s|FR60s|HiLo D|HiLo S|Vira em").split("|")
    return f"""<!doctype html><html lang=pt-br><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Scanner</title><style>
body{{background:#0b0b0f;color:#e8e8ea;font-family:system-ui,-apple-system,sans-serif;margin:0;padding:16px}}
h1{{font-size:19px;margin:0 0 4px}} .sub{{color:#8a8a93;font-size:13px;margin-bottom:14px}}
.nav a{{color:#9ab;margin-right:14px;font-size:14px;text-decoration:none}}
.nav{{margin-bottom:12px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{text-align:left;padding:7px 8px;color:#8a8a93;font-weight:600;border-bottom:1px solid #26262e;
position:sticky;top:0;background:#0b0b0f;white-space:nowrap}}
td{{padding:6px 8px;border-bottom:1px solid #18181f;white-space:nowrap}}
tr:hover td{{background:#15151c}} a{{color:#8ab4ff;text-decoration:none}} a:hover{{text-decoration:underline}} .g{{color:#6b6b75;font-size:11px}}
.wrap{{overflow-x:auto}}
</style><body>
<h1>Scanner — B3, EUA e cripto</h1>
<div class=sub>{selo_data}</div>
<div class=sub>Calculado em {CACHE["quando"].strftime("%d/%m/%Y as %H:%M")} (Brasilia) · {len(dados)} ativos ·
HiLo 5 · ADX 14,14 · IFR 9 · FR contra IBOV / SPX / BTC</div>
<div class=nav><a href="/">Todos</a><a href="/?grupo=B3">B3</a><a href="/?grupo=EUA">EUA</a>
<a href="/?grupo=CRIPTO">Cripto</a><a href="/json">JSON</a><a href="/?forcar=1">Recalcular</a></div>
<div class=wrap><table><tr>{''.join(f'<th>{h}</th>' for h in cab)}</tr>
{''.join(linhas)}</table></div></body></html>"""


# -------------------------------------------------------------- sonda
# O WebFetch do Claude as vezes nao alcanca o site (o servico dorme no plano
# gratuito e a checagem de robots falha). Entao a sonda tambem escreve no log
# do servidor na partida, que e um caminho que sempre funciona.
def _sondar_e_registrar():
    try:
        import json as _json
        print("DIAGNOSTICO_INICIO", flush=True)
        for parte, valor in diag.rodar_tudo().items():
            print("DIAGNOSTICO " + parte + " " + _json.dumps(valor, default=str),
                  flush=True)
        print("DIAGNOSTICO_FIM", flush=True)
    except Exception as e:
        print("DIAGNOSTICO_ERRO " + repr(e)[:300], flush=True)


if os.environ.get("SONDAR", "1") == "1":
    threading.Thread(target=_sondar_e_registrar, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
