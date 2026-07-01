# VLIW Kernel Optimization Plan

## Objective

Produce the fastest correct implementation of `KernelBuilder.build_kernel` for Anthropic's original VLIW/SIMD simulator, measured only by the official frozen submission harness, without modifying simulator behavior, tests, or reference kernels.

## Acceptance Criteria

- AC-1: Official correctness passes under `tests/submission_tests.py`.
- AC-2: Forbidden files remain unchanged: `tests/**`, `problem.py`, and `tests/frozen_problem.py`.
- AC-3: Every promoted candidate has recorded evidence from `tools/eval_kernel.py`.
- AC-4: First performance milestone: official cycles below `1450`.
- AC-5: Stretch performance milestone: official cycles below `1300`.
- AC-6: Frontier performance milestone: official cycles below `1000`.
- AC-7: Final implementation is explainable as legitimate VLIW/SIMD scheduling and arithmetic optimization, not test manipulation, monkeypatching, or hidden harness dependence.

## Constraints

- Allowed final implementation surface: `perf_takehome.py`, plus local support files under `docs/` and `tools/`.
- Do not edit `tests/`, `problem.py`, or `tests/frozen_problem.py`.
- Do not monkeypatch `Machine`, `reference_kernel2`, `unittest`, `random`, import paths, or the submission harness.
- Do not depend on GPU availability; this task is CPU-only simulation even when run on an H800 host.
- Treat `tests/frozen_problem.py` as the authoritative ISA and simulator.
- The public harness checks final `inp_values`; index writes are optional only insofar as value correctness is preserved.
- Preserve correctness for the official workload: `forest_height=10`, `rounds=16`, `batch_size=256`.
- Small custom tests may be used for debugging, but promotion requires official harness evidence.

## Commands

Use the bundled Python if the system Python is older than 3.10:

```bash
/Users/rayw/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/submission_tests.py
```

Portable wrapper:

```bash
tools/eval_kernel.py
```

Instruction diagnostics:

```bash
tools/analyze_instrs.py
```

Remote CPU-only evaluation may use:

```bash
/home/wanrui/.venvs/torch210-h800-bench/bin/python tools/eval_kernel.py --python /home/wanrui/.venvs/torch210-h800-bench/bin/python
```

## Execution Mode

Default to a lightweight implementation loop, not the full RLCR planning shell.

The planning shell is useful for a fresh problem, but this repository already has:

- A frozen objective and acceptance criteria in this file.
- Baseline evidence in `candidates.jsonl` and `.humanize/evals/results.jsonl`.
- A saved `gpt-5.5:xhigh` Codex ISA review under `.humanize/skill/` when running remotely.
- A narrow evaluator and static analyzer under `tools/`.

For this task, the main loop is:

1. Implement one focused candidate in `perf_takehome.py`.
2. Run `tools/analyze_instrs.py`.
3. Run `tools/eval_kernel.py`.
4. Record the candidate in `candidates.jsonl`.
5. Promote only correct improvements; repair or revert failed candidates.
6. Ask Codex `gpt-5.5:xhigh` for review only after a meaningful candidate or before a high-risk legality change.

Do not spend additional rounds on plan compliance, quizzes, bitlesson selection, task-agent setup, or other scaffold work unless the user explicitly asks for it. Those steps have already consumed enough context and are not the bottleneck.

## Workflow Rules

1. Read `docs/vliw-draft.md`, `problem.py`, `tests/frozen_problem.py`, and `perf_takehome.py` before implementation.
2. Maintain `candidates.jsonl` for meaningful candidates. Include candidate id, parent id, summary, cycle count, status, and reason.
3. Run `tools/eval_kernel.py` after every meaningful candidate.
4. Use `tools/analyze_instrs.py` after every candidate that changes instruction generation.
5. Promote only candidates that improve cycles while preserving AC-1 and AC-2.
6. If a candidate fails correctness, record the failure mode and either repair it directly or revert that candidate's changes.
7. Below 1300 cycles, run an explicit anti-cheat audit before marking the work complete.

## Tasks

| ID | Type | Acceptance Criteria | Task |
| --- | --- | --- | --- |
| task1 | coding | AC-1, AC-2, AC-3 | Verify `tools/eval_kernel.py` and `tools/analyze_instrs.py` run on the current baseline and record the baseline in `candidates.jsonl`. |
| task2 | analyze | AC-7 | Ask Codex to review the frozen ISA and identify legal high-value optimization families, with special attention to same-bundle writeback hazards and anti-cheat boundaries. |
| task3 | coding | AC-1, AC-3 | Implement the first scratch-resident SIMD candidate: vectorize values/indices by `VLEN=8`, keep indices in scratch, and store only final values. |
| task4 | coding | AC-1, AC-3 | Add safe VLIW packing for independent vector ALU/load/store/flow slots, respecting end-of-cycle visibility. |
| task5 | coding | AC-1, AC-3 | Rewrite legal hash stages with `valu multiply_add` and validate against frozen reference outputs. |
| task6 | coding | AC-1, AC-3, AC-4 | Pipeline multiple vector groups to overlap gather load slots with hash/index work until cycles are below 1450 or the bottleneck is clearly documented. |
| task7 | analyze | AC-5, AC-7 | Ask Codex to audit any sub-1450 candidate for correctness risks, hidden harness dependence, and remaining cycle bottlenecks. |
| task8 | coding | AC-1, AC-3, AC-5 | Attempt stretch optimizations toward sub-1300 cycles, including wrap timing specialization and deeper static scheduling if they remain explainable. |
| task9 | analyze | AC-6, AC-7 | If approaching sub-1000, ask Codex for an adversarial review of legality and whether the result could be explained without relying on modified tests or simulator behavior. |
| task10 | coding | AC-1, AC-2, AC-3, AC-7 | Finalize the best candidate, remove dead scaffolding, run final `tools/eval_kernel.py`, and summarize the final cycle evidence. |

## Candidate Record Format

Append one JSON object per meaningful candidate to `candidates.jsonl`:

```json
{"id":"c001","parent":null,"summary":"starter baseline","cycles":147734,"status":"baseline","reason":"initial repository state"}
```

Statuses should be one of `baseline`, `promoted`, `rejected`, or `superseded`.

## Completion Criteria

The loop is complete when all non-frontier acceptance criteria are satisfied and no legitimate optimization candidate currently under consideration is expected to improve the best cycle count within the remaining iteration budget. AC-6 is a frontier target, not a reason to keep invalid or speculative changes.
