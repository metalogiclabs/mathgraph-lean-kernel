#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>

static void *work(void *argument) {
    uintptr_t iterations = (uintptr_t)argument;
    __asm__ volatile("1: sub $1, %0; jne 1b" : "+r"(iterations) : : "cc");
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    uintptr_t iterations = strtoull(argv[1], NULL, 10);
    if (iterations == 0) return 2;
    pthread_t threads[4];
    for (unsigned i = 0; i < 4; i++) {
        if (pthread_create(&threads[i], NULL, work, (void *)iterations) != 0) return 3;
    }
    for (unsigned i = 0; i < 4; i++) {
        if (pthread_join(threads[i], NULL) != 0) return 4;
    }
    return 0;
}
