#!/usr/bin/env python3
"""Gera piloto_valores.tex e tabela_piloto.tex a partir das metricas calculadas por analise.py."""
import json, glob, os, sys
import pandas as pd

kit = os.path.dirname(os.path.abspath(__file__))
art = sys.argv[1]
fig = os.path.join(kit, "figuras")
por = pd.read_csv(os.path.join(fig, "metricas_por_execucao.csv")).sort_values("execucao")
agg = pd.read_csv(os.path.join(fig, "metricas_agregadas.csv")).iloc[0]
br = lambda x, d=3: f"{x:.{d}f}".replace(".", "{,}")
meta = json.load(open(sorted(glob.glob(os.path.join(kit, "dados", "*_meta.json")))[0]))
freqs = pd.concat([pd.read_csv(f).freq_mhz for f in glob.glob(os.path.join(kit, "dados", "*_exec*.csv"))])
freq = f"{freqs.iloc[0]:.0f}" if freqs.nunique() == 1 else f"{freqs.min():.0f}--{freqs.max():.0f}"

with open(os.path.join(art, "piloto_valores.tex"), "w") as f:
    f.write(f"\\newcommand{{\\PilotoN}}{{{len(por)}}}\n")
    f.write(f"\\newcommand{{\\PilotoCarga}}{{{meta['fases_s']['carga']}}}\n")
    f.write(f"\\newcommand{{\\ISmedia}}{{{br(agg.IS_media)}}}\n")
    f.write(f"\\newcommand{{\\ISicInf}}{{{br(agg.IS_ic95_inf)}}}\n")
    f.write(f"\\newcommand{{\\ISicSup}}{{{br(agg.IS_ic95_sup)}}}\n")
    f.write(f"\\newcommand{{\\CVmedio}}{{{br(agg.CV_medio)}}}\n")
    f.write(f"\\newcommand{{\\FreqVM}}{{{freq}}}\n")

with open(os.path.join(art, "tabela_piloto.tex"), "w") as f:
    f.write("\\begin{tabular}{lrrrrr}\n\\toprule\n")
    f.write("Execução & $V_0$ & $V_{ss}$ & IS & $Q_{max}$ & CV \\\\\n\\midrule\n")
    for _, r in por.iterrows():
        f.write(f"{int(r.execucao)} & {r.V0:.0f} & {r.Vss:.0f} & {br(r.IS)} & {br(r.Qmax)} & {br(r.CV)} \\\\\n")
    f.write("\\midrule\n")
    f.write(f"Média & {agg.V0_media:.0f} & {agg.Vss_media:.0f} & {br(agg.IS_media)} & {br(agg.Qmax_media)} & {br(agg.CV_medio)} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")
os.makedirs(os.path.join(art, "figuras"), exist_ok=True)
for n in ("fig_protocolo.pdf", "fig_vazao_normalizada.pdf"):
    os.system(f"cp '{os.path.join(fig, n)}' '{os.path.join(art, 'figuras', n)}'")
f2=open(os.path.join(art, "piloto_valores.tex"), "a"); f2.write(f"\\newcommand{{\\ISmediaEN}}{{{agg.IS_media:.3f}}}\n"); f2.close()
print(open(os.path.join(art, "piloto_valores.tex")).read())
