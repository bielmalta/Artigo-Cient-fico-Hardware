/*
 * worker.c - carga sintetica de CPU com trabalho fixo por unidade.
 * Uso: ./worker <duracao_s> <id>
 * Imprime, a cada segundo, "id,segundo,unidades" (unidades de trabalho concluidas naquele segundo).
 * Cada unidade executa a mesma quantidade de operacoes de ponto flutuante e inteiras,
 * de modo que a vazao (unidades/s) so muda se o processador mudar de velocidade.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

static double agora(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

/* Unidade de trabalho: cadeia de multiplica-soma (FP) + hash inteiro (xorshift). */
static volatile double sumidouro;
static void unidade(void) {
    double a = 1.0000001, b = 0.9999999, x = 1.0;
    uint64_t h = 88172645463325252ULL;
    for (int i = 0; i < 200000; i++) {
        x = x * a + b;
        x = x * b - a;
        h ^= h << 13; h ^= h >> 7; h ^= h << 17;
    }
    sumidouro = x + (double)(h & 0xff);
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "uso: %s duracao_s id\n", argv[0]); return 1; }
    double dur = atof(argv[1]);
    int id = atoi(argv[2]);
    setvbuf(stdout, NULL, _IOLBF, 0);
    double t0 = agora(), prox = t0 + 1.0;
    long cont = 0; int seg = 0;
    while (1) {
        unidade();
        cont++;
        double t = agora();
        if (t >= prox) {
            printf("%d,%d,%ld\n", id, seg, cont);
            cont = 0; seg++; prox += 1.0;
            if (t - t0 >= dur) break;
        }
    }
    return 0;
}
