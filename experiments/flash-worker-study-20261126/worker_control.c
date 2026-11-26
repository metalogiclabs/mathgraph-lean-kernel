#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>

/* Three exact application instructions per iteration, in every worker.
 * Library/thread-start instructions are deliberately inside the measured total.
 */
static void *worker(void *argument) {
    uint64_t iterations = *(uint64_t *)argument;
    uint64_t remaining = iterations;
    uint64_t total = 0;
    __asm__ volatile(
        "1: inc %[total]\n\tdec %[remaining]\n\tjnz 1b"
        : [total] "+r"(total), [remaining] "+r"(remaining)
        : : "cc");
    if (total != iterations) abort();
    return NULL;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    unsigned count = (unsigned)strtoul(argv[1], NULL, 10);
    uint64_t iterations = strtoull(argv[2], NULL, 10);
    if (count < 1 || count > 4 || iterations == 0) return 2;
    pthread_t threads[4];
    for (unsigned i = 0; i < count; ++i)
        if (pthread_create(&threads[i], NULL, worker, &iterations)) abort();
    for (unsigned i = 0; i < count; ++i)
        if (pthread_join(threads[i], NULL)) abort();
    return 0;
}
