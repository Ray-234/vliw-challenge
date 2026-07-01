#!/usr/bin/env python3
"""Static instruction diagnostics for generated VLIW programs."""

from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perf_takehome import KernelBuilder  # noqa: E402
from problem import SLOT_LIMITS, SCRATCH_SIZE  # noqa: E402


WRITE_DEST_FIRST = {"alu", "valu", "load"}
FLOW_WRITE_OPS = {"select", "add_imm", "vselect", "coreid"}


def build_kernel(forest_height: int, rounds: int, batch_size: int) -> KernelBuilder:
    kb = KernelBuilder()
    n_nodes = 2 ** (forest_height + 1) - 1
    kb.build_kernel(forest_height, n_nodes, batch_size, rounds)
    return kb


def slot_write_ranges(engine: str, slot: tuple[Any, ...]) -> list[tuple[int, int]]:
    if not slot:
        return []
    op = slot[0]
    if engine == "store" or engine == "debug":
        return []
    if engine == "flow" and op not in FLOW_WRITE_OPS:
        return []
    if engine not in WRITE_DEST_FIRST and engine != "flow":
        return []
    if len(slot) < 2 or not isinstance(slot[1], int):
        return []
    dest = slot[1]
    width = 8 if (engine == "valu" or op in {"vselect", "vbroadcast", "multiply_add"}) else 1
    return [(dest, dest + width)]


def analyze(forest_height: int, rounds: int, batch_size: int) -> dict[str, Any]:
    kb = build_kernel(forest_height, rounds, batch_size)
    bundles = kb.instrs

    slot_counts: Counter[str] = Counter()
    op_counts: Counter[str] = Counter()
    max_slots: dict[str, int] = defaultdict(int)
    slot_limit_violations = []
    duplicate_write_bundles = []

    for pc, bundle in enumerate(bundles):
        writes: list[tuple[int, int, str, tuple[Any, ...]]] = []
        for engine, slots in bundle.items():
            slot_counts[engine] += len(slots)
            max_slots[engine] = max(max_slots[engine], len(slots))
            if len(slots) > SLOT_LIMITS.get(engine, 0):
                slot_limit_violations.append(
                    {"pc": pc, "engine": engine, "slots": len(slots), "limit": SLOT_LIMITS.get(engine)}
                )
            for slot in slots:
                if slot:
                    op_counts[f"{engine}:{slot[0]}"] += 1
                for start, end in slot_write_ranges(engine, slot):
                    writes.append((start, end, engine, slot))

        overlaps = []
        for i, left in enumerate(writes):
            for right in writes[i + 1 :]:
                if left[0] < right[1] and right[0] < left[1]:
                    overlaps.append({"left": left[:3], "right": right[:3]})
        if overlaps:
            duplicate_write_bundles.append({"pc": pc, "overlaps": overlaps[:8]})

    utilization = {}
    for engine, limit in SLOT_LIMITS.items():
        if engine == "debug":
            continue
        denom = max(1, len(bundles) * limit)
        utilization[engine] = round(slot_counts[engine] / denom, 6)

    return {
        "workload": {
            "forest_height": forest_height,
            "rounds": rounds,
            "batch_size": batch_size,
            "n_nodes": 2 ** (forest_height + 1) - 1,
        },
        "bundles": len(bundles),
        "scratch_used": kb.scratch_ptr,
        "scratch_size": SCRATCH_SIZE,
        "slot_counts": dict(sorted(slot_counts.items())),
        "max_slots_per_bundle": dict(sorted(max_slots.items())),
        "slot_utilization_upper_bound": utilization,
        "op_counts": dict(sorted(op_counts.items())),
        "slot_limit_violations": slot_limit_violations,
        "duplicate_write_bundles": duplicate_write_bundles[:20],
        "duplicate_write_bundle_count": len(duplicate_write_bundles),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forest-height", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = analyze(args.forest_height, args.rounds, args.batch_size)
    print(json.dumps(report, indent=None if args.json else 2, sort_keys=True))
    if report["slot_limit_violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
