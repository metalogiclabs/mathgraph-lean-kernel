/* Independently authored DynamoRIO diagnostic, separate from checker code.
 * Requires private code caches so each generated update can address stable
 * thread-local storage directly. Produces executed basic-block frequencies.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "drreg.h"
#include "drx.h"
#include <stdint.h>

#define BUCKETS 4096
typedef struct block_count {
    uint64_t executions;
    app_pc pc;
    unsigned instructions;
    struct block_count *next;
} block_count;
typedef struct { block_count *buckets[BUCKETS]; } thread_profile;
static int tls_index;
static void *output_lock;
static file_t output;
static app_pc executable_start, executable_end;
static uint64_t total;
static unsigned threads;

static void require(bool condition) {
    if (!condition) { dr_fprintf(STDERR, "FLASH_PROFILE_INVALID\n"); dr_abort(); }
}

static void start_thread(void *context) {
    thread_profile *profile = dr_thread_alloc(context, sizeof(*profile));
    for (unsigned i = 0; i < BUCKETS; i++) profile->buckets[i] = NULL;
    require(drmgr_set_tls_field(context, tls_index, profile));
}

static void finish_thread(void *context) {
    thread_profile *profile = drmgr_get_tls_field(context, tls_index);
    require(profile != NULL);
    uint64_t subtotal = 0;
    dr_mutex_lock(output_lock);
    for (unsigned i = 0; i < BUCKETS; i++) {
        block_count *block = profile->buckets[i];
        while (block != NULL) {
            block_count *next = block->next;
            uintptr_t pc = (uintptr_t)block->pc;
            bool main = pc >= (uintptr_t)executable_start && pc < (uintptr_t)executable_end;
            uintptr_t address = main ? pc - (uintptr_t)executable_start : pc;
            dr_fprintf(output, "%c\t%llx\t%u\t%llu\n", main ? 'M' : 'L',
                (unsigned long long)address, block->instructions,
                (unsigned long long)block->executions);
            subtotal += block->executions * block->instructions;
            dr_thread_free(context, block, sizeof(*block));
            block = next;
        }
    }
    total += subtotal;
    threads++;
    dr_mutex_unlock(output_lock);
    dr_thread_free(context, profile, sizeof(*profile));
}

static dr_emit_flags_t analyze(void *context, void *tag, instrlist_t *block,
    bool trace, bool translating, void **data) {
    unsigned instructions = 0;
    app_pc pc = NULL;
    for (instr_t *instruction = instrlist_first_app(block); instruction != NULL;
         instruction = instr_get_next_app(instruction)) {
        if (pc == NULL) pc = instr_get_app_pc(instruction);
        instructions++;
    }
    if (instructions == 0) { *data = NULL; return DR_EMIT_DEFAULT; }
    require(pc != NULL);
    thread_profile *profile = drmgr_get_tls_field(context, tls_index);
    require(profile != NULL);
    unsigned bucket = (((uintptr_t)pc >> 3) ^ instructions) & (BUCKETS - 1);
    block_count *entry = profile->buckets[bucket];
    while (entry != NULL && (entry->pc != pc || entry->instructions != instructions)) entry = entry->next;
    if (entry == NULL) {
        entry = dr_thread_alloc(context, sizeof(*entry));
        entry->executions = 0;
        entry->pc = pc;
        entry->instructions = instructions;
        entry->next = profile->buckets[bucket];
        profile->buckets[bucket] = entry;
    }
    *data = entry;
    return DR_EMIT_DEFAULT;
}

static dr_emit_flags_t instrument(void *context, void *tag, instrlist_t *block,
    instr_t *instruction, bool trace, bool translating, void *data) {
    if (drmgr_is_first_instr(context, instruction) && data != NULL) {
        block_count *entry = data;
        require(drx_insert_counter_update(context, block, instruction,
            SPILL_SLOT_MAX + 1, &entry->executions, 1, DRX_COUNTER_64BIT));
    }
    return DR_EMIT_DEFAULT;
}

static void finish_process(void) {
    dr_fprintf(STDERR, "FLASH_PROFILE instructions=%llu threads=%u\n",
        (unsigned long long)total, threads);
    dr_close_file(output);
    require(drmgr_unregister_tls_field(tls_index));
    dr_mutex_destroy(output_lock);
    drx_exit(); drreg_exit(); drmgr_exit();
}

DR_EXPORT void dr_client_main(client_id_t id, int argc, const char *argv[]) {
    require(dr_using_all_private_caches());
    require(argc == 2);
    output = dr_open_file(argv[1], DR_FILE_WRITE_OVERWRITE | DR_FILE_ALLOW_LARGE);
    require(output != INVALID_FILE);
    module_data_t *executable = dr_get_main_module();
    require(executable != NULL);
    executable_start = executable->start;
    executable_end = executable->end;
    dr_free_module_data(executable);
    require(drmgr_init());
    drreg_options_t registers = { sizeof(registers), 3, false };
    require(drreg_init(&registers) == DRREG_SUCCESS);
    require(drx_init());
    output_lock = dr_mutex_create();
    tls_index = drmgr_register_tls_field();
    require(tls_index >= 0);
    require(drmgr_register_thread_init_event(start_thread));
    require(drmgr_register_thread_exit_event(finish_thread));
    require(drmgr_register_exit_event(finish_process));
    require(drmgr_register_bb_instrumentation_event(analyze, instrument, NULL));
}
