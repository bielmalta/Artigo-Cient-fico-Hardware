#!/usr/bin/env python3
"""
analise.py - calcula as metricas de sustentacao de desempenho e gera graficos.

Uso: python3 analise.py dados/ figuras/
Metricas por execucao (fase de carga, descartando os 5 s iniciais e os 2 s finais):
  V0   = mediana da vazao nos primeiros 30 s validos (processador "frio")
  Vss  = mediana da vazao nos ultimos 60 s de carga (regime sustentado)
  IS   = Vss / V0                      (indice de sustentacao; 1,0 = sem perda)
  Qmax = 1 - min(media movel 10 s) / V0 (maior queda observada)
  t95  = primeiro instante em que a media movel de 10 s fica abaixo de 0,95*V0 (s desde o inicio da carga)
  CV   = desvio-padrao / media da vazao em toda a carga
  rho  = correlacao de Spearman entre vazao e temperatura / frequencia (quando houver sensores)
Agregado por condicao: media de IS com intervalo de confianca de 95% por bootstrap.
"""
import glob, os, sys, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

DESCARTE_INI, DESCARTE_FIM, JAN_INI, JAN_FIM, MM = 5, 2, 30, 60, 10


def metricas(df):
    c = df[df.fase == "carga"].copy()
    c["v"] = pd.to_numeric(c.vazao_unid_s, errors="coerce")
    c = c.iloc[DESCARTE_INI:len(c) - DESCARTE_FIM].reset_index(drop=True)
    c["t_carga"] = np.arange(len(c)) + DESCARTE_INI
    v0 = c.v.iloc[:JAN_INI].median()
    vss = c.v.iloc[-JAN_FIM:].median()
    mm = c.v.rolling(MM).mean()
    abaixo = c.t_carga[mm < 0.95 * v0]
    r = {"V0": v0, "Vss": vss, "IS": vss / v0, "Qmax": 1 - mm.min() / v0,
         "t95_s": float(abaixo.iloc[0]) if len(abaixo) else None,
         "CV": c.v.std() / c.v.mean()}
    for col, nome in [("temp_c", "rho_temp"), ("freq_mhz", "rho_freq")]:
        x = pd.to_numeric(c[col], errors="coerce")
        ok = x.notna() & c.v.notna()
        r[nome] = spearmanr(x[ok], c.v[ok]).statistic if ok.sum() > 10 and x[ok].nunique() > 1 else None
        r[col.replace("_c", "_max_c").replace("_mhz", "_min_mhz")] = (
            (x.max() if "temp" in col else x.min()) if ok.any() else None)
    return r, c


def ic_bootstrap(vals, n=10000, seed=42):
    vals = np.asarray(vals, dtype=float)
    if len(vals) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    medias = rng.choice(vals, (n, len(vals)), replace=True).mean(axis=1)
    return tuple(np.percentile(medias, [2.5, 97.5]))


def main(pasta, saida):
    os.makedirs(saida, exist_ok=True)
    linhas, series = [], {}
    for arq in sorted(glob.glob(os.path.join(pasta, "*_exec*.csv"))):
        nome = os.path.basename(arq)[:-4]
        cond, ex = nome.rsplit("_exec", 1)
        df = pd.read_csv(arq)
        r, c = metricas(df)
        r.update(condicao=cond, execucao=int(ex))
        linhas.append(r)
        series.setdefault(cond, []).append((int(ex), df, c))
    tab = pd.DataFrame(linhas)
    tab.to_csv(os.path.join(saida, "metricas_por_execucao.csv"), index=False)

    agg = []
    for cond, g in tab.groupby("condicao"):
        lo, hi = ic_bootstrap(g.IS)
        agg.append({"condicao": cond, "n": len(g), "V0_media": g.V0.mean(), "Vss_media": g.Vss.mean(),
                    "IS_media": g.IS.mean(), "IS_ic95_inf": lo, "IS_ic95_sup": hi,
                    "Qmax_media": g.Qmax.mean(), "CV_medio": g.CV.mean(),
                    "execucoes_com_t95": int(g.t95_s.notna().sum())})
    agg = pd.DataFrame(agg)
    agg.to_csv(os.path.join(saida, "metricas_agregadas.csv"), index=False)
    print(tab.to_string(index=False))
    print(agg.to_string(index=False))

    # Figura 1: vazao normalizada ao longo da carga (todas as execucoes)
    plt.rcParams.update({"font.size": 9, "font.family": "serif"})
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    for cond, lst in series.items():
        for ex, df, c in sorted(lst, key=lambda z: z[0]):
            v0 = c.v.iloc[:JAN_INI].median()
            ax.plot(c.t_carga, c.v.rolling(MM, min_periods=1).mean() / v0, lw=1, label=f"{cond}, exec. {ex}")
    ax.axhline(0.95, ls="--", lw=0.8, color="gray")
    ax.text(5, 0.952, "limiar de 95%", fontsize=7, color="gray", va="bottom")
    ax.set_xlabel("Tempo desde o início da carga (s)")
    ax.set_ylabel("Vazão / $V_0$ (média móvel 10 s)")
    ax.set_ylim(0.7, 1.06)
    ax.legend(fontsize=7, loc="lower left", frameon=False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(saida, "fig_vazao_normalizada.pdf"))
    fig.savefig(os.path.join(saida, "fig_vazao_normalizada.png"), dpi=200)

    # Figura 2: uma execucao completa (uso de CPU e vazao) para ilustrar o protocolo
    cond, lst = next(iter(series.items()))
    ex, df, c = sorted(lst, key=lambda z: z[0])[0]
    fig, ax1 = plt.subplots(figsize=(6.2, 2.4))
    ax1.plot(df.t_s, pd.to_numeric(df.uso_cpu_pct, errors="coerce"), color="tab:gray", lw=1, label="Uso de CPU (%)")
    ax1.set_ylabel("Uso de CPU (%)")
    ax1.set_xlabel("Tempo (s)")
    ax2 = ax1.twinx()
    v = pd.to_numeric(df.vazao_unid_s, errors="coerce")
    ax2.plot(df.t_s, v, color="tab:blue", lw=1, label="Vazão (unid./s)")
    ax2.set_ylabel("Vazão (unid./s)")
    ax2.set_ylim(0, (v.max() or 1) * 1.15)
    ini = df.t_s[df.fase == "carga"].min(); fim = df.t_s[df.fase == "carga"].max()
    for x in (ini, fim):
        ax1.axvline(x, ls=":", color="k", lw=0.8)
    ax1.text(ini / 2, 50, "repouso", ha="center", fontsize=7)
    ax1.text((ini + fim) / 2, 50, "carga", ha="center", fontsize=7)
    ax1.text((fim + df.t_s.max()) / 2, 50, "recup.", ha="center", fontsize=7)
    h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(saida, "fig_protocolo.pdf"))
    fig.savefig(os.path.join(saida, "fig_protocolo.png"), dpi=200)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dados", sys.argv[2] if len(sys.argv) > 2 else "figuras")
