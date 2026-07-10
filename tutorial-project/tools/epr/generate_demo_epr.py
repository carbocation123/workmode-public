#!/usr/bin/env python3
"""Generate a deterministic Bruker-style PAR/SPC teaching spectrum.

The output is synthetic and must never be represented as instrument data.
SPC contains little-endian IEEE float32 values; PAR records the field axis and
acquisition-like metadata used by the portable conversion and scan tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
from pathlib import Path


G_CONST = 714.477
DEFAULT_POINTS = 1024
DEFAULT_FIELD_START_G = 3100.0
DEFAULT_SWEEP_G = 800.0
DEFAULT_MF_GHZ = 9.8
SEED = 20260710


def derivative_gaussian(field: float, *, center: float, width: float, amplitude: float) -> float:
    z = (field - center) / width
    return -amplitude * z * math.exp(-0.5 * z * z)


def generate_signal(
    *,
    points: int = DEFAULT_POINTS,
    field_start: float = DEFAULT_FIELD_START_G,
    sweep: float = DEFAULT_SWEEP_G,
    mf_ghz: float = DEFAULT_MF_GHZ,
) -> tuple[list[float], list[float], dict[str, float]]:
    fields = [field_start + index * sweep / (points - 1) for index in range(points)]
    center_a = G_CONST * mf_ghz / 2.003
    center_b = G_CONST * mf_ghz / 1.965
    rng = random.Random(SEED)
    signal: list[float] = []
    for index, field in enumerate(fields):
        baseline = 1.0e-5 * (field - (field_start + sweep / 2))
        deterministic_noise = 0.008 * math.sin(index * 0.37) + 0.005 * math.sin(index * 1.13)
        random_noise = rng.gauss(0.0, 0.004)
        value = (
            derivative_gaussian(field, center=center_a, width=4.2, amplitude=1.4)
            + derivative_gaussian(field, center=center_b, width=3.2, amplitude=0.35)
            + baseline
            + deterministic_noise
            + random_noise
        )
        signal.append(value)
    return fields, signal, {
        "signal_a_g": 2.003,
        "signal_a_center_G": center_a,
        "signal_b_g": 1.965,
        "signal_b_center_G": center_b,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_demo(output_dir: Path, stem: str, *, force: bool = False) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    par_path = output_dir / f"{stem}.par"
    spc_path = output_dir / f"{stem}.spc"
    manifest_path = output_dir / f"{stem}_generation.json"
    existing = [path for path in (par_path, spc_path, manifest_path) if path.exists()]
    if existing and not force:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"拒绝覆盖已有模拟原始文件：{names}；确认重建请加 --force")

    fields, signal, centers = generate_signal()
    spc_path.write_bytes(struct.pack(f"<{len(signal)}f", *signal))
    par_lines = [
        "TIT Workmode Public simulated EPR teaching spectrum",
        "SIMULATED TRUE",
        f"ANZ {len(signal)}",
        f"GST {fields[0]:.6f}",
        f"GSI {fields[-1] - fields[0]:.6f}",
        f"HCF {(fields[0] + fields[-1]) / 2:.6f}",
        f"HSW {fields[-1] - fields[0]:.6f}",
        f"MF {DEFAULT_MF_GHZ:.6f}",
        "MP 2.000",
        "TE 77.0",
        "JDA 2026-07-10",
        "JTM 20:00",
        f"MIN {min(signal):.9g}",
        f"MAX {max(signal):.9g}",
    ]
    par_path.write_text("\n".join(par_lines) + "\n", encoding="utf-8")
    manifest = {
        "simulated": True,
        "purpose": "Workmode Public tutorial; not instrument data",
        "seed": SEED,
        "points": len(signal),
        "spc_encoding": "little-endian IEEE float32",
        "field_start_G": fields[0],
        "field_end_G": fields[-1],
        "microwave_frequency_GHz": DEFAULT_MF_GHZ,
        "embedded_signals": centers,
        "files": {
            par_path.name: {"sha256": sha256(par_path)},
            spc_path.name: {"sha256": sha256(spc_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return par_path, spc_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="生成确定性的 Bruker 风格模拟 EPR PAR/SPC")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stem", default="demo_epr")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有模拟文件")
    args = parser.parse_args()
    par, spc, manifest = write_demo(args.output_dir, args.stem, force=args.force)
    print(f"SIMULATED PAR: {par}")
    print(f"SIMULATED SPC: {spc} ({spc.stat().st_size} bytes)")
    print(f"MANIFEST: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
