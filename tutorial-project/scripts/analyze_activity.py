"""Analyze the synthetic CO-oxidation CSV without modifying raw data."""

from __future__ import annotations

import argparse
import csv
import struct
import zlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REQUIRED = {
    "sample_id",
    "batch_id",
    "timestamp",
    "temperature_C",
    "co_in_ppm",
    "co_out_ppm",
    "flow_sccm",
    "status",
}
COLORS = {"C300": (38, 99, 235), "C450": (22, 163, 74), "C600": (220, 60, 70)}


def approximate_t50(points: list[tuple[float, float]]) -> float | None:
    ordered = sorted(points)
    for left, right in zip(ordered, ordered[1:]):
        t1, c1 = left
        t2, c2 = right
        if c1 == 50:
            return t1
        if (c1 - 50) * (c2 - 50) <= 0 and c1 != c2:
            return t1 + (50 - c1) * (t2 - t1) / (c2 - c1)
    return None


def draw_line(pixels: bytearray, width: int, height: int, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        if 0 <= x0 < width and 0 <= y0 < height:
            offset = (y0 * width + x0) * 3
            pixels[offset : offset + 3] = bytes(color)
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def write_png(path: Path, series: dict[str, list[tuple[float, float]]]) -> None:
    width, height = 900, 540
    pixels = bytearray([255] * width * height * 3)
    left, right, top, bottom = 80, 850, 40, 480
    for fraction in range(0, 11):
        y = bottom - round((bottom - top) * fraction / 10)
        draw_line(pixels, width, height, (left, y), (right, y), (225, 229, 235))
    draw_line(pixels, width, height, (left, top), (left, bottom), (40, 40, 40))
    draw_line(pixels, width, height, (left, bottom), (right, bottom), (40, 40, 40))

    def transform(point: tuple[float, float]) -> tuple[int, int]:
        temperature, conversion = point
        x = left + round((temperature - 100) / 200 * (right - left))
        y = bottom - round(conversion / 100 * (bottom - top))
        return x, y

    for sample, points in sorted(series.items()):
        color = COLORS.get(sample, (90, 90, 90))
        mapped = [transform(point) for point in sorted(points)]
        for first, second in zip(mapped, mapped[1:]):
            draw_line(pixels, width, height, first, second, color)
        for x, y in mapped:
            for offset in range(-4, 5):
                draw_line(pixels, width, height, (x - 4, y + offset), (x + 4, y + offset), color)

    raw = b"".join(b"\x00" + bytes(pixels[row * width * 3 : (row + 1) * width * 3]) for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw, level=9))
    payload += chunk(b"IEND", b"")
    path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    input_hash_before = args.input_csv.read_bytes()
    with args.input_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = REQUIRED - set(reader.fieldnames or [])
        if missing_columns:
            raise SystemExit(f"Missing columns: {sorted(missing_columns)}")
        source_rows = list(reader)

    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    processed: list[dict[str, str]] = []
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for line_number, row in enumerate(source_rows, start=2):
        key = (row["sample_id"], row["timestamp"], row["temperature_C"])
        if key in seen:
            warnings.append(f"line {line_number}: duplicate record {key}; excluded after first occurrence")
            continue
        seen.add(key)
        if not row["co_in_ppm"] or not row["co_out_ppm"]:
            warnings.append(f"line {line_number}: missing CO signal for {row['sample_id']} at {row['temperature_C']} C; excluded")
            continue
        co_in = float(row["co_in_ppm"])
        co_out = float(row["co_out_ppm"])
        if co_in <= 0:
            warnings.append(f"line {line_number}: non-positive inlet CO; excluded")
            continue
        conversion = (co_in - co_out) / co_in * 100
        item = dict(row)
        item["conversion_pct"] = f"{conversion:.3f}"
        processed.append(item)
        series[row["sample_id"]].append((float(row["temperature_C"]), conversion))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed_path = args.output_dir / "activity-processed.csv"
    fields = list(source_rows[0]) + ["conversion_pct"]
    with processed_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(processed)

    summary_lines = [
        "# Activity analysis summary",
        "",
        f"- Source: `{args.input_csv.as_posix()}`",
        "- Script: `scripts/analyze_activity.py`",
        "- Conversion: `(CO_in - CO_out) / CO_in * 100`",
        f"- Generated: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- Source rows: {len(source_rows)}; valid rows: {len(processed)}",
        "",
        "## Data-quality warnings",
        "",
    ]
    summary_lines.extend(f"- {warning}" for warning in warnings)
    summary_lines.extend(["", "## Approximate T50", "", "| Sample | Valid points | T50 (C) |", "|---|---:|---:|"])
    for sample, points in sorted(series.items()):
        t50 = approximate_t50(points)
        summary_lines.append(f"| {sample} | {len(points)} | {t50:.1f} |" if t50 is not None else f"| {sample} | {len(points)} | not bracketed |")
    summary_lines.extend([
        "",
        "## Figure",
        "",
        "- File: `conversion-curves.png`",
        "- X-axis: temperature, 100-300 C",
        "- Y-axis: CO conversion, 0-100%",
        "- Series: C300 = blue; C450 = green; C600 = red",
        "",
        "## Interpretation boundary",
        "",
        "The activity curves compare this synthetic run only. They do not establish oxygen-vacancy concentration or reaction mechanism.",
    ])
    (args.output_dir / "activity-summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    write_png(args.output_dir / "conversion-curves.png", series)

    if args.input_csv.read_bytes() != input_hash_before:
        raise SystemExit("Raw input changed during analysis")
    print(f"Processed {len(processed)} valid rows; warnings={len(warnings)}; output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
