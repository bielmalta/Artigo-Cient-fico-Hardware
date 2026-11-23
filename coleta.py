#!/usr/bin/env python3
"""
coleta.py - executa o protocolo repouso -> carga -> recuperacao e registra, a cada segundo:
vazao da carga (unidades/s), utilizacao de CPU, frequencia media e temperatura (quando disponiveis).

Uso:
  python3 coleta.py --rotulo notebookA_mesa --execucao 1 --repouso 60 --carga 600 --recuperacao 120
Saida: dados/<rotulo>_exec<N>.csv  e  dados/<rotulo>_exec<N>_meta.json

Linux: temperatura via /sys/class/thermal ou psutil; frequencia via /proc/cpuinfo ou cpufreq.
macOS: execute com sudo e --powermetrics para registrar frequencia e nivel de pressao termica.
Windows: use WSL2 (temperatura em geral indisponivel) ou registre a temperatura com outra ferramenta.
"""
import argparse, glob, json, os, platform, re, subprocess, sys, threading, time
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))


def compilar_worker():
    exe = os.path.join(AQUI, "worker")
    src = os.path.join(AQUI, "worker.c")
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        subprocess.run(["cc", "-O2", "-o", exe, src], check=True)
    return exe


# ---------- sensores ----------
def ler_temperatura():
    vals = []
    for z in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            v = int(open(z).read().strip()) / 1000.0
            if 0 < v < 130:
                vals.append(v)
        except Exception:
            pass
    if vals:
        return max(vals)
    try:
        import psutil
        t = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
        vals = [s.current for lst in t.values() for s in lst if s.current]
        return max(vals) if vals else None
    except Exception:
        return None


def ler_frequencia():
    fs = []
    for f in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq"):
        try:
            fs.append(int(open(f).read()) / 1000.0)
        except Exception:
            pass
    if fs:
        return sum(fs) / len(fs)
    try:
        mhz = [float(m) for m in re.findall(r"cpu MHz\s*:\s*([\d.]+)", open("/proc/cpuinfo").read())]
        return sum(mhz) / len(mhz) if mhz else None
    except Exception:
        return None


class UsoCPU:
    def __init__(self):
        self.ant = self._ler()

    def _ler(self):
        try:
            c = open("/proc/stat").readline().split()[1:]
            c = list(map(int, c))
            return sum(c), c[3] + c[4]
        except Exception:
            return None

    def amostrar(self):
        atual = self._ler()
        if atual is None or self.ant is None:
            try:
                import psutil
                return psutil.cpu_percent(interval=None)
            except Exception:
                return None
        dt, di = atual[0] - self.ant[0], atual[1] - self.ant[1]
        self.ant = atual
        return 100.0 * (dt - di) / dt if dt > 0 else None


class PowerMetrics:
    """macOS (sudo): le frequencia media dos clusters e nivel de pressao termica."""
    def __init__(self):
        self.freq, self.pressao = None, None
        self.p = subprocess.Popen(["powermetrics", "--samplers", "cpu_power,thermal", "-i", "1000"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        fs = []
        for linha in self.p.stdout:
            m = re.search(r"(P|E)?-?Cluster HW active frequency:\s*([\d.]+)\s*MHz", linha)
            if m:
                fs.append(float(m.group(2)))
            m = re.search(r"Current pressure level:\s*(\w+)", linha)
            if m:
                self.pressao = m.group(1)
                if fs:
                    self.freq = max(fs)
                fs = []

    def parar(self):
        self.p.terminate()


# ---------- protocolo ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotulo", required=True, help="ex.: notebookA_mesa")
    ap.add_argument("--execucao", type=int, required=True)
    ap.add_argument("--repouso", type=int, default=60)
    ap.add_argument("--carga", type=int, default=600)
    ap.add_argument("--recuperacao", type=int, default=120)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--powermetrics", action="store_true")
    ap.add_argument("--saida", default=os.path.join(AQUI, "dados"))
    a = ap.parse_args()

    os.makedirs(a.saida, exist_ok=True)
    exe = compilar_worker()
    pm = PowerMetrics() if a.powermetrics else None
    uso = UsoCPU()

    contagem = {}          # segundo_global -> unidades
    trava = threading.Lock()
    t_ini = time.monotonic()

    def ler_worker(proc):
        for linha in proc.stdout:
            seg = int(time.monotonic() - t_ini)
            try:
                n = int(linha.strip().split(",")[2])
            except Exception:
                continue
            with trava:
                contagem[seg] = contagem.get(seg, 0) + n

    total = a.repouso + a.carga + a.recuperacao
    procs, linhas = [], []
    proximo = t_ini + 1.0
    for s in range(total):
        if s == a.repouso:
            for i in range(a.workers):
                p = subprocess.Popen([exe, str(a.carga), str(i)], stdout=subprocess.PIPE, text=True)
                threading.Thread(target=ler_worker, args=(p,), daemon=True).start()
                procs.append(p)
        time.sleep(max(0.0, proximo - time.monotonic()))
        proximo += 1.0
        fase = "repouso" if s < a.repouso else ("carga" if s < a.repouso + a.carga else "recuperacao")
        freq = pm.freq if pm else ler_frequencia()
        linhas.append([s, fase, uso.amostrar(), freq, ler_temperatura(), pm.pressao if pm else None])
        if s % 30 == 0:
            print(f"[{s:4d}/{total}] {fase}", file=sys.stderr)
    for p in procs:
        p.wait()
    if pm:
        pm.parar()
    time.sleep(0.5)

    arq = os.path.join(a.saida, f"{a.rotulo}_exec{a.execucao}.csv")
    with open(arq, "w") as f:
        f.write("t_s,fase,uso_cpu_pct,freq_mhz,temp_c,pressao_termica,vazao_unid_s\n")
        for s, fase, u, fr, te, pr in linhas:
            v = contagem.get(s, 0) if fase == "carga" else ""
            fmt = lambda x: "" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))
            f.write(",".join([str(s), fase, fmt(u), fmt(fr), fmt(te), fmt(pr), str(v)]) + "\n")
    meta = {
        "rotulo": a.rotulo, "execucao": a.execucao, "inicio": datetime.now().isoformat(),
        "plataforma": platform.platform(), "processador": platform.processor() or platform.machine(),
        "nucleos_logicos": os.cpu_count(), "workers": a.workers,
        "fases_s": {"repouso": a.repouso, "carga": a.carga, "recuperacao": a.recuperacao},
        "python": sys.version.split()[0],
    }
    json.dump(meta, open(arq.replace(".csv", "_meta.json"), "w"), indent=2, ensure_ascii=False)
    print("salvo:", arq, file=sys.stderr)


if __name__ == "__main__":
    main()
