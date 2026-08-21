#!/usr/bin/env python3
"""Prospective Test 2a: does the game actually require semantic JOIN?

This is a structural eligibility assay, not evidence that an LLM can perform the
JOIN.  The world deliberately separates local residual vocabularies.  JOIN is
frozen before the downstream transfer target is selected.

The key causal comparison is not "history vs no history".  Every non-serial arm
may retain all observations.  The distinction is whether the controller is
allowed to construct cross-channel equivalence coordinates that were not present
in any local vocabulary.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
import statistics
from collections import deque
from dataclasses import dataclass
from pathlib import Path


CHANNEL_FACTORS = {
    "A": [0, 1, 5],
    "B": [1, 2, 5],
    "C": [2, 3, 5],
    "D": [3, 4, 5],
    "E": [4, 0, 5],
}
N_LATENT = 6


@dataclass(frozen=True)
class Channel:
    factors: tuple[int, ...]
    flips: tuple[int, ...]
    tokens: tuple[str, ...]


def make_world(seed: int) -> tuple[random.Random, dict[str, Channel]]:
    rng = random.Random(seed)
    channels: dict[str, Channel] = {}
    for name, base in CHANNEL_FACTORS.items():
        factors = list(base)
        rng.shuffle(factors)
        flips = [rng.randrange(2) for _ in factors]
        # Local names intentionally carry no cross-channel semantic clue.
        tokens = [f"{name}:{rng.randrange(1_000_000):06d}" for _ in factors]
        channels[name] = Channel(tuple(factors), tuple(flips), tuple(tokens))
    return rng, channels


def observe(z: tuple[int, ...] | list[int], ch: Channel) -> tuple[int, ...]:
    return tuple(z[f] ^ flip for f, flip in zip(ch.factors, ch.flips))


def node_list(channels: dict[str, Channel]) -> list[tuple[str, int]]:
    return [(name, i) for name, ch in channels.items() for i in range(len(ch.factors))]


def inferred_join(
    samples: list[dict[str, tuple[int, ...]]], channels: dict[str, Channel]
) -> dict[tuple[str, int], list[tuple[tuple[str, int], int]]]:
    """Invent cross-channel coordinates from equality/complement signatures.

    Edge parity p means value(v) = value(u) XOR p.  No latent factor ids or
    channel construction metadata are available here.
    """
    nodes = node_list(channels)
    graph = {n: [] for n in nodes}
    values = {n: [sample[n[0]][n[1]] for sample in samples] for n in nodes}
    for i, u in enumerate(nodes):
        for v in nodes[i + 1 :]:
            if u[0] == v[0]:
                continue
            a, b = values[u], values[v]
            if all(x == y for x, y in zip(a, b)):
                parity = 0
            elif all((x ^ 1) == y for x, y in zip(a, b)):
                parity = 1
            else:
                continue
            graph[u].append((v, parity))
            graph[v].append((u, parity))
    return graph


def oracle_join(channels: dict[str, Channel]):
    nodes = node_list(channels)
    graph = {n: [] for n in nodes}
    for i, u in enumerate(nodes):
        cu, iu = u
        fu = channels[cu].factors[iu]
        flip_u = channels[cu].flips[iu]
        for v in nodes[i + 1 :]:
            cv, iv = v
            if cu == cv:
                continue
            if channels[cv].factors[iv] == fu:
                parity = flip_u ^ channels[cv].flips[iv]
                graph[u].append((v, parity))
                graph[v].append((u, parity))
    return graph


def wrong_join(rng: random.Random, channels: dict[str, Channel]):
    """A deliberately shuffled mapping with the same graph-size opportunity."""
    nodes = node_list(channels)
    graph = {n: [] for n in nodes}
    by_channel = {c: [(c, i) for i in range(len(ch.factors))] for c, ch in channels.items()}
    names = list(channels)
    for a_i, ca in enumerate(names):
        for cb in names[a_i + 1 :]:
            # One arbitrary relation per pair: plausible-looking but semantically wrong.
            u = rng.choice(by_channel[ca])
            v = rng.choice(by_channel[cb])
            p = rng.randrange(2)
            graph[u].append((v, p))
            graph[v].append((u, p))
    return graph


def find_target_coordinate(graph, source: tuple[str, int], target_channel: str):
    q = deque([(source, 0)])
    seen = {source}
    while q:
        node, parity = q.popleft()
        if node[0] == target_channel:
            return node, parity
        for nxt, edge_parity in graph[node]:
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, parity ^ edge_parity))
    return None


def learn_source_coordinate(
    source_obs: list[tuple[int, ...]], labels: list[int]
) -> tuple[int, int]:
    """Common downstream learner: choose local coordinate + polarity by calibration."""
    ranked = []
    for i in range(len(source_obs[0])):
        for decode_flip in (0, 1):
            correct = sum((o[i] ^ decode_flip) == y for o, y in zip(source_obs, labels))
            ranked.append((correct, -i, -decode_flip, i, decode_flip))
    _, _, _, i, decode_flip = max(ranked)
    return i, decode_flip


def eval_join(
    graph,
    source_node: tuple[str, int],
    source_decode_flip: int,
    target_channel: str,
    test_z: list[tuple[int, ...]],
    target_factor: int,
    channels: dict[str, Channel],
) -> float:
    mapped = find_target_coordinate(graph, source_node, target_channel)
    if mapped is None:
        return 0.5
    (target_node, relation_flip) = mapped
    target_i = target_node[1]
    pred = [
        observe(z, channels[target_channel])[target_i] ^ relation_flip ^ source_decode_flip
        for z in test_z
    ]
    truth = [z[target_factor] for z in test_z]
    return sum(p == y for p, y in zip(pred, truth)) / len(truth)


def run_world(seed: int) -> dict[str, float | int | str]:
    rng, channels = make_world(seed)

    # ---------------- JOIN PHASE ----------------
    # No downstream label or transfer task exists yet from the controller's view.
    join_z = [tuple(rng.randrange(2) for _ in range(N_LATENT)) for _ in range(64)]
    unlabeled = [{name: observe(z, ch) for name, ch in channels.items()} for z in join_z]

    # Freeze all representations before choosing the downstream target.
    d_graph = inferred_join(unlabeled, channels)
    e_graph = oracle_join(channels)
    c_graph = wrong_join(rng, channels)

    # ---------------- DOWNSTREAM PHASE ----------------
    # Only now choose an unseen transfer problem.  Source and target have at least
    # one shared latent factor, but their local token vocabularies are disjoint.
    tasks: list[tuple[str, str, int]] = []
    names = list(channels)
    for a_i, source in enumerate(names):
        for target in names[a_i + 1 :]:
            common = set(channels[source].factors) & set(channels[target].factors)
            tasks.extend((source, target, f) for f in sorted(common))
    source, target, factor = rng.choice(tasks)

    calibration_z = [tuple(rng.randrange(2) for _ in range(N_LATENT)) for _ in range(24)]
    source_obs = [observe(z, channels[source]) for z in calibration_z]
    labels = [z[factor] for z in calibration_z]
    source_i, source_decode_flip = learn_source_coordinate(source_obs, labels)
    source_node = (source, source_i)

    # Exhaustive latent combinations make held-out scoring deterministic and balanced.
    test_z = list(itertools.product((0, 1), repeat=N_LATENT))
    rng.shuffle(test_z)

    # A: latest/single residual.  B: full history but local-only accumulation.
    # F: union of original vocabularies, no new cross-channel relation.  Once the
    # label is learned in source coordinates, all three lack an admissible map into
    # the target namespace.  Their optimal no-alignment prediction on this balanced
    # test is chance.  This is intentional: Test 2a asks whether the world *requires*
    # a representation-changing operation, not whether an LLM can perform one.
    majority = 1 if sum(labels) > len(labels) / 2 else 0
    truth = [z[factor] for z in test_z]
    local_only = sum(majority == y for y in truth) / len(truth)

    d = eval_join(d_graph, source_node, source_decode_flip, target, test_z, factor, channels)
    e = eval_join(e_graph, source_node, source_decode_flip, target, test_z, factor, channels)
    c = eval_join(c_graph, source_node, source_decode_flip, target, test_z, factor, channels)

    return {
        "seed": seed,
        "source": source,
        "target": target,
        "factor": factor,
        "A_serial": local_only,
        "B_full_history_local": local_only,
        "C_wrong_join": c,
        "F_union_vocab_no_new_coords": local_only,
        "D_inferred_semantic_join": d,
        "E_oracle_join": e,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=int, default=512)
    ap.add_argument("--out", type=Path, default=Path("semantic_join_results.csv"))
    args = ap.parse_args()

    rows = [run_world(seed) for seed in range(args.worlds)]
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    arms = [k for k in rows[0] if k not in {"seed", "source", "target", "factor"}]
    means = {arm: statistics.mean(float(r[arm]) for r in rows) for arm in arms}

    print("SEMANTIC_JOIN_SEALED_WORLD_TEST2A")
    print(f"worlds={args.worlds}")
    print("JOIN_FROZEN_BEFORE_DOWNSTREAM_TARGET=1")
    for arm in arms:
        print(f"{arm}={means[arm]:.6f}")

    b = means["B_full_history_local"]
    f = means["F_union_vocab_no_new_coords"]
    c = means["C_wrong_join"]
    d = means["D_inferred_semantic_join"]
    e = means["E_oracle_join"]
    print(f"D_minus_B={d-b:+.6f}")
    print(f"D_minus_F={d-f:+.6f}")
    print(f"oracle_gap_E_minus_D={e-d:+.6f}")

    # Eligibility gates for an LLM version of Test 2.  Passing these does NOT
    # support Developmental Intelligence; it only says the sealed world is not
    # another disguised full-history/set-intersection game.
    checks = {
        "D_beats_B_by_25pp": d - b >= 0.25,
        "D_beats_F_by_25pp": d - f >= 0.25,
        "D_near_oracle": e - d <= 0.05 and d >= 0.90,
        "wrong_join_not_competitive": c <= 0.65,
        "local_controls_near_chance": b <= 0.55 and f <= 0.55,
    }
    for name, ok in checks.items():
        print(f"GATE {name}={'PASS' if ok else 'FAIL'}")
    passed = all(checks.values())
    print(
        "VERDICT="
        + (
            "ASSAY_ELIGIBLE__FREEZE_PROTOCOL_AND_TEST_LLM_JOIN"
            if passed
            else "ASSAY_REJECTED__DO_NOT_RUN_LLM"
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
