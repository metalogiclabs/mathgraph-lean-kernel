#!/usr/bin/env python3
"""Emit blind Test 2b JOIN packets.

Packets contain only heterogeneous channel-local token names and compact response
signatures from the JOIN phase. No latent ids, flips, downstream targets, labels,
or scoring metadata are emitted. The LLM must freeze cross-channel relations from
these packets before scoring.
"""
from __future__ import annotations
import json
from pathlib import Path
from run import make_world, observe, N_LATENT

N_WORLDS = 12
N_SAMPLES = 24

def bits_to_hex(bits):
    x = 0
    for b in bits:
        x = (x << 1) | int(b)
    width = (len(bits) + 3) // 4
    return f"{x:0{width}x}"

def main():
    packets = []
    for seed in range(N_WORLDS):
        rng, channels = make_world(seed)
        join_z = [tuple(rng.randrange(2) for _ in range(N_LATENT)) for _ in range(N_SAMPLES)]
        coords = []
        for cname, ch in channels.items():
            obs = [observe(z, ch) for z in join_z]
            for i, tok in enumerate(ch.tokens):
                sig = [row[i] for row in obs]
                coords.append({"channel": cname, "token": tok, "signature_hex": bits_to_hex(sig)})
        packets.append({"world": seed, "n_samples": N_SAMPLES, "coordinates": coords})
    out = Path("test2b_blind_packets.json")
    out.write_text(json.dumps({"protocol":"TEST2B_BLIND_JOIN_V1","worlds":packets}, indent=2))
    print(out.read_text())

if __name__ == "__main__":
    main()
