/* Independently authored diagnostic client for the DynamoRIO SDK.
 * Counts decoded application instructions, including libraries, in every
 * application thread. This is a software metric, not retired hardware events.
 * Thread-private caches are mandatory: each generated update embeds the
 * address of its own thread's counter. Only exit-time summation takes a lock.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "drreg.h"
#include "drx.h"
#include <stdint.h>

typedef struct { uint64_t instructions; } thread_count;
static int tls_index;
static void *sum_lock;
static uint64_t sum;
static unsigned threads;

static void require(bool condition) {
    if (!condition) { dr_fprintf(STDERR, "FLASH_COUNTER_INVALID\n"); dr_abort(); }
}

static void start_thread(void *context) {
    thread_count *counter = dr_thread_alloc(context, sizeof(*counter));
    counter->instructions = 0;
    require(drmgr_set_tls_field(context, tls_index, counter));
}

static void finish_thread(void *context) {
    thread_count *counter = drmgr_get_tls_field(context, tls_index);
    require(counter != NULL);
    dr_mutex_lock(sum_lock);
    sum += counter->instructions;
    threads++;
    dr_mutex_unlock(sum_lock);
    dr_thread_free(context, counter, sizeof(*counter));
}

static dr_emit_flags_t analyze(void *context, void *tag, instrlist_t *block,
    bool trace, bool translating, void **data) {
    uintptr_t instructions = 0;
    for (instr_t *instruction = instrlist_first(block); instruction != NULL;
         instruction = instr_get_next(instruction)) {
        if (instr_is_app(instruction)) instructions++;
    }
    *data = (void *)instructions;
    return DR_EMIT_DEFAULT;
}

static dr_emit_flags_t instrument(void *context, void *tag, instrlist_t *block,
    instr_t *instruction, bool trace, bool translating, void *data) {
    if (drmgr_is_first_instr(context, instruction) && data != NULL) {
        thread_count *counter = drmgr_get_tls_field(context, tls_index);
        require(counter != NULL);
        require(drx_insert_counter_update(context, block, instruction,
            SPILL_SLOT_MAX + 1, &counter->instructions, (int)(uintptr_t)data,
            DRX_COUNTER_64BIT));
    }
    return DR_EMIT_DEFAULT;
}

static void finish_process(void) {
    dr_fprintf(STDERR, "FLASH_COUNTER instructions=%llu threads=%u\n",
        (unsigned long long)sum, threads);
    require(drmgr_unregister_tls_field(tls_index));
    dr_mutex_destroy(sum_lock);
    drx_exit();
    drreg_exit();
    drmgr_exit();
}

DR_EXPORT void dr_client_main(client_id_t id, int argc, const char *argv[]) {
    require(dr_using_all_private_caches());
    require(drmgr_init());
    drreg_options_t registers = { sizeof(registers), 3, false };
    require(drreg_init(&registers) == DRREG_SUCCESS);
    require(drx_init());
    sum_lock = dr_mutex_create();
    tls_index = drmgr_register_tls_field();
    require(tls_index >= 0);
    require(drmgr_register_thread_init_event(start_thread));
    require(drmgr_register_thread_exit_event(finish_thread));
    require(drmgr_register_exit_event(finish_process));
    require(drmgr_register_bb_instrumentation_event(analyze, instrument, NULL));
}
