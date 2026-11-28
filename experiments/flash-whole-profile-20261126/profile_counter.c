/* SPDX-License-Identifier: Apache-2.0
 * MathGraph diagnostic: same block-counting rule as instruction_counter.c,
 * with exclusive symbol attribution decided at translation, not at execution.
 * DynamoRIO public API: https://dynamorio.org/API_samples.html
 * This is not hardware retirement or an official Arena score. Inlined work is
 * charged to the containing compiled symbol; library code is reported apart.
 */
#include "dr_api.h"
#include "drmgr.h"
#include "drreg.h"
#include "drx.h"
#include "symbol_map.h"

#if !defined(X86_64)
# error This diagnostic is qualified only for x86-64.
#endif

typedef struct { uint64 value; byte padding[56]; } Counter;
static Counter counts[SYMBOL_COUNT + 2] __attribute__((aligned(64)));
static app_pc main_start, main_end;

static uint
symbol_index(app_pc pc)
{
    if (pc < main_start || pc >= main_end)
        return SYMBOL_COUNT; /* Libraries or other application code. */
    uint64 offset = (uint64)(pc - main_start) + IMAGE_BASE;
    uint lo = 0, hi = SYMBOL_COUNT;
    while (lo < hi) {
        uint mid = lo + (hi - lo) / 2;
        if (symbols[mid].lo <= offset)
            lo = mid + 1;
        else
            hi = mid;
    }
    if (lo > 0 && offset < symbols[lo - 1].hi)
        return lo - 1;
    return SYMBOL_COUNT + 1; /* Main executable, no sized text symbol. */
}

static dr_emit_flags_t
analyze(void *context, void *tag, instrlist_t *block, bool trace, bool translating,
        void **result)
{
    uint count = 0;
    for (instr_t *i = instrlist_first_app(block); i != NULL; i = instr_get_next_app(i))
        ++count;
    /* Count and symbol index fit in a pointer without allocating per-block data. */
    DR_ASSERT(count < 65536);
    uint index = symbol_index(dr_fragment_app_pc(tag));
    *result = (void *)(((ptr_uint_t)index << 16) | count);
    return DR_EMIT_DEFAULT;
}

static dr_emit_flags_t
insert(void *context, void *tag, instrlist_t *block, instr_t *instruction,
       bool trace, bool translating, void *analysis)
{
    if (instruction != instrlist_first_app(block))
        return DR_EMIT_DEFAULT;
    ptr_uint_t packed = (ptr_uint_t)analysis;
    uint count = packed & 65535;
    uint index = packed >> 16;
    if (count == 0)
        return DR_EMIT_DEFAULT;
    DR_ASSERT(index < SYMBOL_COUNT + 2);
    if (!drx_insert_counter_update(context, block, instruction, SPILL_SLOT_MAX + 1,
                                  &counts[index].value, (int)count,
                                  DRX_COUNTER_64BIT | DRX_COUNTER_LOCK))
        dr_abort();
    return DR_EMIT_DEFAULT;
}

static void
finished(void)
{
    uint64 total = 0;
    for (uint i = 0; i < SYMBOL_COUNT + 2; ++i) {
        if ((uint64)-1 - total < counts[i].value)
            dr_abort();
        total += counts[i].value;
        if (counts[i].value)
            dr_fprintf(STDERR, "MATHGRAPH_SYMBOL %u %llu\n", i,
                       (unsigned long long)counts[i].value);
    }
    dr_fprintf(STDERR, "MATHGRAPH_DYNAMIC_INSTRUCTIONS %llu\n",
               (unsigned long long)total);
    drx_exit();
    drreg_exit();
    drmgr_exit();
}

DR_EXPORT void
dr_client_main(client_id_t id, int argc, const char *argv[])
{
    drreg_options_t options = { sizeof(options), 1, false };
    dr_set_client_name("MathGraph exclusive compiled-symbol instruction diagnostic",
                       "https://github.com/metalogiclabs/mathgraph-lean-kernel");
    module_data_t *main = dr_get_main_module();
    if (main == NULL)
        dr_abort();
    main_start = main->start;
    main_end = main->end;
    dr_free_module_data(main);
    if (!drmgr_init() || !drx_init() || drreg_init(&options) != DRREG_SUCCESS)
        dr_abort();
    if (!drmgr_register_exit_event(finished) ||
        !drmgr_register_bb_instrumentation_event(analyze, insert, NULL))
        dr_abort();
}
