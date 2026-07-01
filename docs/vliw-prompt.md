# Humanize Entry Prompt

Use this repository as a CPU-only VLIW simulator optimization task.

Start from `docs/vliw-plan.md`. The official scoring path is `tests/submission_tests.py` with `tests/frozen_problem.py`. Do not modify `tests/`, `problem.py`, or `tests/frozen_problem.py`.

Composer configuration:

- Claude Code
- Model: `claude-opus-4-8`
- Reasoning effort: `high`

Reviewer configuration:

- Codex
- Model and effort: `gpt-5.5:xhigh`

Suggested Humanize command:

```text
claude -p "$(cat docs/vliw-prompt.md)" --model claude-opus-4-8 --effort high --betas context-1m-2025-08-07 --permission-mode bypassPermissions
```

Do not use `/humanize:start-rlcr-loop` as the default path for this repository anymore. It repeatedly spent time in plan/task/bitlesson scaffolding before producing a candidate. Use direct implementation mode: edit `perf_takehome.py`, run `tools/analyze_instrs.py`, run `tools/eval_kernel.py`, record `candidates.jsonl`, and ask Codex `gpt-5.5:xhigh` only for targeted review.

The H800 host may be used as a remote CPU machine, but this challenge does not use the GPU and must not use H800 SXM/PCIe performance assumptions.

## Direct Implementation Prompt

Work in the current repository. Use `docs/vliw-plan.md` as the standing plan, but do not run extra planning scaffolds.

Model policy:

- Composer: Claude Code `claude-opus-4-8`, high effort, 1M context beta when available.
- Reviewer: Codex `gpt-5.5:xhigh` only, used after meaningful candidates or before high-risk legality changes.
- Do not invoke haiku, sonnet, task agents, plan compliance agents, bitlesson selector, code-simplifier, or non-flagship helper models.

Immediate loop:

1. Briefly inspect `tests/frozen_problem.py`, `problem.py`, and `perf_takehome.py` for exact ISA names and hazards.
2. Implement the smallest correct optimized candidate in `perf_takehome.py`.
3. Prefer scratch-resident SIMD vectors, legal `valu multiply_add` hash fusions, and safe bundle packing.
4. Run `tools/analyze_instrs.py`.
5. Run `tools/eval_kernel.py`.
6. Append candidate evidence to `candidates.jsonl`.
7. If correctness fails, repair or revert before continuing.
