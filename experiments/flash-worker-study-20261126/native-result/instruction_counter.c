/* MathGraph bounded diagnostic, using the public DynamoRIO API.
 * API references: https://dynamorio.org/group__drx.html and API_samples.html.
 * This counts application instructions in executed basic blocks, including
 * shared libraries. It is not a hardware retired-instruction measurement.
 * The locked 64-bit update is essential: the checker creates several threads
 * even when configured with one checking worker.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "drreg.h"
#include "drx.h"

#if !defined(X86_64)
#    error This diagnostic is qualified only for x86-64.
#endif

static uint64 instruction_total __attribute__((aligned(64)));

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
insert(void *context, void *tag, instrlist_t *block, instr_t *instruction, bool trace,
       bool translating, void *analysis)
{
    if (instruction != instrlist_first_app(block) || analysis == NULL)
        return DR_EMIT_DEFAULT;
    bool ok = drx_insert_counter_update(context, block, instruction,
        SPILL_SLOT_MAX + 1, &instruction_total, (int)(ptr_uint_t)analysis,
        DRX_COUNTER_64BIT | DRX_COUNTER_LOCK);
    if (!ok)
        dr_abort();
    return DR_EMIT_DEFAULT;
}

static void
finished(void)
{
    dr_fprintf(STDERR, "MATHGRAPH_DYNAMIC_INSTRUCTIONS %llu\n",
        (unsigned long long)instruction_total);
    drx_exit();
    drreg_exit();
    drmgr_exit();
}

DR_EXPORT void
dr_client_main(client_id_t id, int argc, const char *argv[])
{
    drreg_options_t options = { sizeof(options), 1, false };
    dr_set_client_name("MathGraph basic-block instruction diagnostic",
        "https://github.com/metalogiclabs/mathgraph-lean-kernel");
    if (!drmgr_init() || !drx_init() || drreg_init(&options) != DRREG_SUCCESS)
        dr_abort();
    if (!drmgr_register_exit_event(finished) ||
        !drmgr_register_bb_instrumentation_event(analyze, insert, NULL))
        dr_abort();
}
