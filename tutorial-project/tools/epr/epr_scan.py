#!/usr/bin/env python3
"""epr_scan.py — Bruker WinEPR .asc 一次性分析助手

读取 Bruker WinEPR 导出的 `.asc`（两列：B[G], Intensity）+ 同名 `.par`，自动：

1. 从 `.par` 解析 MF（微波频率）/ MP / TE / HCF / HSW / 日期 / 时间
2. 按 **g = 714.477 × MF[GHz] / B[G]** 换 g 轴（每条谱用自己的 MF；非共用平均轴）
3. 在指定窗口（默认 g 1.91–2.04）测各区段峰峰值 pp
4. 在用户指定的空白窗口估计噪声，给出 **3× 噪声**检测门限

不做自动物种归属。模拟教程只把峰称为 Signal A / Signal B；真实谱的化学归属必须结合实验条件和独立证据。

用法:
    py -3.11 epr_scan.py <asc_path>
    py -3.11 epr_scan.py <asc_path> --window 1.79 2.15      # 扩展到 Mn 全六线
    py -3.11 epr_scan.py <asc_path> --noise-window 1.945 1.965
    py -3.11 epr_scan.py <asc_path> --mf 9.3210             # 覆盖 .par 的 MF
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# g = (h / μ_B) × ν / B; h/μ_B = 7.1448e-11 T·s; GHz→Hz×1e9, G→T×1e-4
# → g = 714.477 × ν[GHz] / B[G]
G_CONST = 714.477


def parse_par(par_path: Path) -> dict:
    """Bruker WinEPR .par 单行连写 → 字段字典。"""
    txt = par_path.read_text(encoding="utf-8", errors="replace")
    patterns = {
        "HCF": r"\bHCF\s+([\d.eE+\-]+)",
        "HSW": r"\bHSW\s+([\d.eE+\-]+)",
        # MF / MP / TE 都可能被 EMF / Sample 等前缀污染，用负向断言
        "MF":  r"(?<![A-Za-z])MF\s+([\d.eE+\-]+)",
        "MP":  r"(?<![A-Za-z])MP\s+([\d.eE+\-]+)",
        "TE":  r"(?<![A-Za-z])TE\s+([\d.eE+\-]+)",
        "JDA": r"\bJDA\s+(\d{4}-\d{2}-\d{2})",
        "JTM": r"\bJTM\s+(\d{2}:\d{2})",
    }
    return {k: (m.group(1) if (m := re.search(p, txt)) else None) for k, p in patterns.items()}


def parse_asc(asc_path: Path) -> tuple[list[float], list[float]]:
    """两列数据 .asc → (B, I)。前几行 header 自动跳过。"""
    B, I = [], []
    for ln in asc_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = ln.strip().split()
        if len(parts) != 2:
            continue
        try:
            B.append(float(parts[0]))
            I.append(float(parts[1]))
        except ValueError:
            pass
    return B, I


def find_pp(G, B, I, g_lo, g_hi):
    """返回 (n, g@max, B@max, I_max, g@min, B@min, I_min, pp, is_indep) 或 None。

    is_indep = "独立导数对" 判据：I_max > 0 AND I_min < 0。
        - True  → 正负瓣对称完整，可视为独立信号
        - False → I_max 或 I_min 与 0 同号，单边污染（如 Mn 负瓣 tail 落入），
                  本区段 pp 主要来自相邻强线的衰减尾巴而非独立信号
    """
    mask = [(g, b, i) for g, b, i in zip(G, B, I) if g_lo <= g <= g_hi]
    if not mask:
        return None
    g_max = max(mask, key=lambda x: x[2])
    g_min = min(mask, key=lambda x: x[2])
    is_indep = g_max[2] > 0 and g_min[2] < 0
    return (len(mask), g_max[0], g_max[1], g_max[2],
            g_min[0], g_min[1], g_min[2], g_max[2] - g_min[2], is_indep)


def scan_type_name(hsw: float | None) -> str:
    if hsw is None:
        return "?"
    if abs(hsw - 800) < 1:
        return "主扫"
    if abs(hsw - 6000) < 1:
        return "宽扫"
    if abs(hsw - 200) < 1:
        return "精扫"
    return f"HSW={hsw:g}G"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asc_path", help="Bruker .asc 文件路径")
    ap.add_argument("--par", type=Path, default=None,
                    help="PAR 元数据路径；默认使用与 ASC 同名同目录的 .par")
    ap.add_argument("--mf", type=float, default=None,
                    help="手动指定 MF (GHz)；省略则从同名 .par 读")
    ap.add_argument("--window", nargs=2, type=float, default=(1.91, 2.04),
                    metavar=("LO", "HI"),
                    help="分析窗口 g 范围（默认 1.91 2.04）")
    ap.add_argument("--noise-window", nargs=2, type=float, default=(1.94, 1.955),
                    metavar=("LO", "HI"),
                    help="噪声基准 g 范围（默认 1.94 1.955；真实数据应人工选择空白区）")
    args = ap.parse_args()

    asc_path = Path(args.asc_path)
    if not asc_path.is_file():
        print(f"错误: {asc_path} 不存在", file=sys.stderr)
        return 2

    par_path = args.par if args.par is not None else asc_path.with_suffix(".par")
    par = parse_par(par_path) if par_path.is_file() else {}
    MF = args.mf if args.mf is not None else (float(par["MF"]) if par.get("MF") else None)
    if MF is None:
        print("错误: 既未提供 --mf，同名 .par 也读不到 MF", file=sys.stderr)
        return 1

    B, I = parse_asc(asc_path)
    if not B:
        print("错误: .asc 无数据点", file=sys.stderr)
        return 1
    G = [G_CONST * MF / b for b in B]

    print(f"文件: {asc_path.name}")
    if par_path.is_file():
        hsw = float(par["HSW"]) if par.get("HSW") else None
        print(f".par: {par.get('JDA','?')} {par.get('JTM','?')} | "
              f"MF {MF:.4f} GHz | MP {par.get('MP','?')} mW | TE {par.get('TE','?')} K | "
              f"HCF {par.get('HCF','?')} G | HSW {par.get('HSW','?')} G ({scan_type_name(hsw)})")
    else:
        print(f"(.par 不存在，MF 用 --mf={MF})")
    print(f"数据: N={len(B)} pts | B {min(B):.2f}–{max(B):.2f} G | g {min(G):.4f}–{max(G):.4f}")
    print(f"强度: I {min(I):.3e}–{max(I):.3e}")

    # 噪声基准
    nlo, nhi = args.noise_window
    n = find_pp(G, B, I, nlo, nhi)
    if n:
        n_pp = n[7]
        print(f"\n噪声基准（g {nlo}–{nhi}, N={n[0]}）: pp = {n_pp:.3e}  |  3× 门限 = {3*n_pp:.3e}")
    else:
        n_pp = None
        print(f"\n噪声窗 g {nlo}–{nhi} 出界，无法测噪声")

    # 固定窗口仅用于客观扫描，不代表物种归属。
    print(f"\n--- 特征扫（窗口 g {args.window[0]}–{args.window[1]}）---")
    print(f"{'区段':<16}{'N':>4} {'g@max':>8}{'B@max':>9}{'I_max':>12} {'g@min':>8}{'B@min':>9}{'I_min':>12} {'pp':>12}  比门限  独立?")
    regions = [
        ("g 2.025–2.045", 2.025, 2.045),
        ("Signal A 窗",    2.000, 2.025),
        ("g 1.985–2.000", 1.985, 2.000),
        ("g 1.970–1.985", 1.970, 1.985),
        ("Signal B 窗",    1.957, 1.971),
        ("g 1.915–1.935", 1.915, 1.935),
    ]
    for name, lo, hi in regions:
        r = find_pp(G, B, I, lo, hi)
        if r is None:
            print(f"{name:<16}   – (out of range)")
            continue
        n_, gmax, bmax, imax, gmin, bmin, imin, pp, is_indep = r
        ratio = f"{pp/(3*n_pp):.2f}×" if n_pp else "–"
        indep = "✓" if is_indep else "✗(单边)"
        print(f"{name:<16}{n_:>4} {gmax:>8.4f}{bmax:>9.1f}{imax:>12.3e} "
              f"{gmin:>8.4f}{bmin:>9.1f}{imin:>12.3e} {pp:>12.3e}  {ratio:>6}  {indep}")

    # 全窗口
    print(f"\n--- 全窗口 g {args.window[0]}–{args.window[1]} ---")
    r = find_pp(G, B, I, args.window[0], args.window[1])
    if r:
        n_, gmax, bmax, imax, gmin, bmin, imin, pp, is_indep = r
        print(f"N={n_} | I_max={imax:.3e}@g={gmax:.4f}/B={bmax:.1f} | I_min={imin:.3e}@g={gmin:.4f}/B={bmin:.1f} | pp={pp:.3e}")
        if n_pp:
            print(f"全窗 pp / 3× 噪声 = {pp/(3*n_pp):.2f}×")

    print("\n注: '独立?' 列 = ✓(I_max>0 且 I_min<0) 表示窗口内存在完整正负瓣；"
          "\n    这只是谱形检查，不构成物种归属。✗ 表示该窗口可能只有相邻信号尾部或基线漂移。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
