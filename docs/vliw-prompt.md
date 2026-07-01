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
/humanize:start-rlcr-loop docs/vliw-plan.md --yolo --max 20 --codex-model gpt-5.5:xhigh --codex-timeout 5400 --full-review-round 3
```

The H800 host may be used as a remote CPU machine, but this challenge does not use the GPU and must not use H800 SXM/PCIe performance assumptions.
