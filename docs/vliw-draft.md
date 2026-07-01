# VLIW Kernel Optimization Draft

## Problem Summary

Optimize `KernelBuilder.build_kernel` in `perf_takehome.py` for Anthropic's original performance take-home. The submitted program runs on the frozen simulator in `tests/frozen_problem.py`; local changes to `problem.py` or `tests/` must not be used as part of the solution.

The target workload used by the public submission harness is:

- `forest_height = 10`
- `rounds = 16`
- `batch_size = 256`
- `VLEN = 8`
- `N_CORES = 1`

The final output check compares only the final `inp_values` memory range. The reference kernel also updates `inp_indices`, but the public harness does not require final indices to be written back.

## Machine Model Digest

- VLIW bundles execute one cycle each when they contain at least one non-debug engine.
- Slot limits per cycle: `alu=12`, `valu=6`, `load=2`, `store=2`, `flow=1`.
- Effects become visible only after all slots in the current bundle read their inputs. Same-bundle producer-to-consumer dependencies are invalid.
- Scalar memory load/store uses a scratch address that contains the memory address.
- `vload` and `vstore` operate only on contiguous memory.
- `load_offset` can be used to gather lanes from a vector of scratch addresses, but is still constrained by the 2 load slots per cycle.
- `valu` operates on `VLEN=8` contiguous scratch lanes. Useful operations include ordinary vector ALU operations and `multiply_add`.
- Scratch space is `SCRATCH_SIZE=1536` 32-bit words.

## Baseline

The starter implementation is scalar and emits one slot per instruction bundle. It repeatedly reloads indices and values from memory, computes one element at a time, and writes both indices and values after every element-round.

Baseline evidence on the original code:

- `perf_takehome.py Tests.test_kernel_cycles`: `147734` cycles
- `tests/submission_tests.py`: correctness passes, speed thresholds fail

## Optimization Directions

Promising directions, roughly in expected value order:

1. Process inputs in groups of `VLEN=8` lanes and keep active `idx` and `val` vectors in scratch.
2. Load all initial values once with `vload`; do not write intermediate values until the final result.
3. Maintain indices in scratch and skip final index stores, since the submission harness checks only values.
4. Generate static unrolled code for the known workload shape instead of runtime loops.
5. Use `load_offset` over vector address registers to gather tree node values.
6. Pack independent slots into VLIW bundles while respecting end-of-cycle writeback.
7. Rewrite suitable hash stages with `valu multiply_add`; for stages shaped like `(a + c) + (a << k)`, use `a * (2^k + 1) + c` modulo 32 bits.
8. Pipeline gather, hash, index update, and next-round preparation across multiple vector groups.
9. Specialize tree wrap timing for `height=10` and `rounds=16` where correctness permits.

## Risks

- Same-bundle read-after-write mistakes can silently produce wrong values.
- Scratch allocation can exceed 1536 words when over-pipelining vector groups.
- Low cycle counts below 1300 require especially strict anti-cheat review, because the public README notes early invalid submissions below that range.
- Data-dependent flow control may make cycles differ across random inputs; official cycle evidence must come from the frozen submission harness.
- Edits to `tests/`, `problem.py`, or `tests/frozen_problem.py` invalidate the result even if local tests pass.

## Evaluation

Use the official harness as the source of truth:

```bash
python tests/submission_tests.py
```

Use the local wrapper for repeatable Humanize/Codex loop evidence:

```bash
tools/eval_kernel.py
```

Use the static instruction analyzer for diagnosis only:

```bash
tools/analyze_instrs.py
```
