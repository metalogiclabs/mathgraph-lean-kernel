/* Independently authored MathGraph diagnostic prototype. x86-64 only.
 * Counts application basic-block instructions, including libraries, in a
 * raw TLS slot. Merges once at thread exit. No hardware/PMU claim.
 * API: https://dynamorio.org/group__drreg.html and dr_tools.h in the pinned SDK.
 * Qualification is bounded to the retained no-fork controls/checker runs.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "drreg.h"

#if !defined(X86_64)
#error This prototype requires x86-64.
#endif

static reg_id_t tls_segment;
static uint tls_offset;
static int pointer_slot;
static void *sum_lock;
static uint64 total;
static uint threads_started, threads_finished;

static void
thread_started(void *context)
{
    uint64 *counter = (uint64 *)((byte *)dr_get_dr_segment_base(tls_segment) + tls_offset);
    *counter = 0;
    if (!drmgr_set_tls_field(context, pointer_slot, counter))
        dr_abort();
    dr_mutex_lock(sum_lock);
    ++threads_started;
    dr_mutex_unlock(sum_lock);
}

static void
thread_finished(void *context)
{
    /* The callback may run on a different thread. Use the saved pointer from
     * this context, never the current thread's segment base. */
    uint64 *counter = drmgr_get_tls_field(context, pointer_slot);
    if (counter == NULL)
        dr_abort();
    dr_mutex_lock(sum_lock);
    total += *counter;
    ++threads_finished;
    dr_mutex_unlock(sum_lock);
    drmgr_set_tls_field(context, pointer_slot, NULL);
}

static dr_emit_flags_t
analyze(void *context, void *tag, instrlist_t *block, bool trace, bool translating,
        void **result)
{
    uint count = 0;
    for (instr_t *i = instrlist_first_app(block); i != NULL; i = instr_get_next_app(i))
        ++count;
    *result = (void *)(ptr_uint_t)count;
    return DR_EMIT_DEFAULT;
}

static dr_emit_flags_t
insert(void *context, void *tag, instrlist_t *block, instr_t *instruction,
       bool trace, bool translating, void *analysis)
{
    if (instruction != instrlist_first_app(block) || analysis == NULL)
        return DR_EMIT_DEFAULT;
    if (drreg_reserve_aflags(context, block, instruction) != DRREG_SUCCESS)
        dr_abort();
    instrlist_meta_preinsert(block, instruction,
        INSTR_CREATE_add(context, dr_raw_tls_opnd(context, tls_segment, tls_offset),
                         OPND_CREATE_INT32((int)(ptr_uint_t)analysis)));
    if (drreg_unreserve_aflags(context, block, instruction) != DRREG_SUCCESS)
        dr_abort();
    return DR_EMIT_DEFAULT;
}

static void
finished(void)
{
    if (threads_started == 0 || threads_started != threads_finished)
        dr_abort();
    dr_fprintf(STDERR, "MATHGRAPH_DYNAMIC_INSTRUCTIONS %llu\n",
               (unsigned long long)total);
    dr_fprintf(STDERR, "MATHGRAPH_COUNTER_THREADS %u\n", threads_finished);
    drmgr_unregister_tls_field(pointer_slot);
    dr_raw_tls_cfree(tls_offset, 1);
    dr_mutex_destroy(sum_lock);
    drreg_exit();
    drmgr_exit();
}

DR_EXPORT void
dr_client_main(client_id_t id, int argc, const char *argv[])
{
    drreg_options_t options = { sizeof(options), 3, false };
    dr_set_client_name("MathGraph thread-local basic-block diagnostic prototype",
        "https://github.com/metalogiclabs/mathgraph-lean-kernel");
    if (!drmgr_init() || drreg_init(&options) != DRREG_SUCCESS ||
        !dr_raw_tls_calloc(&tls_segment, &tls_offset, 1, 0))
        dr_abort();
    pointer_slot = drmgr_register_tls_field();
    sum_lock = dr_mutex_create();
    if (pointer_slot < 0 || sum_lock == NULL ||
        !drmgr_register_thread_init_event(thread_started) ||
        !drmgr_register_thread_exit_event(thread_finished) ||
        !drmgr_register_exit_event(finished) ||
        !drmgr_register_bb_instrumentation_event(analyze, insert, NULL))
        dr_abort();
}
