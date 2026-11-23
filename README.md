# Kit de medição — temperatura e throttling

Mede quanto a vazão de uma carga fixa de CPU cai ao longo de uma carga contínua e registra, a cada segundo, uso de CPU, frequência e temperatura.

## Arquivos
- `worker.c` — carga sintética (trabalho fixo por unidade; compilada automaticamente).
- `coleta.py` — executa o protocolo repouso → carga → recuperação e grava `dados/<condicao>_exec<N>.csv`.
- `analise.py` — calcula V0, Vss, IS, Qmax, t95, CV e correlações; gera tabelas e figuras em `figuras/`.
- `dados/nuvem_controle_exec*.csv` — piloto real já executado (ambiente de controle).

## Requisitos
Compilador C (`cc`/`gcc`/`clang`) e Python 3 com `numpy pandas scipy matplotlib psutil`:
```
pip3 install -r requirements.txt
```

## Protocolo (cada notebook)
1. Notebook na tomada, tampa aberta, brilho fixo, Wi-Fi ligado, **todos os outros programas fechados**.
2. Anote a temperatura ambiente da sala (termômetro ou app do celular).
3. Espere o computador esfriar (10 min parado) antes de cada execução.
4. Rode 5 execuções por condição, alternando a ordem das condições (ex.: mesa, suporte, mesa, suporte…):

Linux (nativo, não em VM):
```
python3 coleta.py --rotulo notebookA_mesa --execucao 1 --repouso 60 --carga 600 --recuperacao 120
```
macOS (frequência e pressão térmica exigem sudo):
```
sudo python3 coleta.py --rotulo notebookB_mesa --execucao 1 --powermetrics --repouso 60 --carga 600 --recuperacao 120
```
Windows: rode no Linux de um pendrive (live USB) ou registre temperatura/frequência em paralelo com HWiNFO (exportar CSV a cada 1 s). **Não use VM**: o piloto mostrou que dentro de máquina virtual a temperatura não é visível e a frequência aparece fixa.

5. Condições sugeridas (fatores): superfície (`mesa` × `suporte` elevado) e alimentação (`tomada` × `bateria`). Use o rótulo `<maquina>_<superficie>_<alimentacao>`.

## Análise
```
python3 analise.py dados figuras
```
Gera `figuras/metricas_por_execucao.csv`, `figuras/metricas_agregadas.csv` e os gráficos usados no artigo.
