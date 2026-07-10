"""
bruker_spc2asc.py
==================

Bruker WinEPR .par + .spc → .asc 文本格式兼容生成器。

适用场景：EPR 软件无法导出 ASCII，但同名 `.par/.spc` 文件完整。

仅依赖标准库（struct）。无 numpy 依赖以减少环境耦合。

用法
----
单文件：
    py -3.11 bruker_spc2asc.py <par 路径>

批量：
    py -3.11 bruker_spc2asc.py <par1> <par2> ...

指定输出（仅单文件时）：
    py -3.11 bruker_spc2asc.py <par> -o <asc 输出路径>

依赖
----
- Python 3.x
- 同目录下应同时有 .par 和 .spc 同名文件

参考
----
PAR 关键字段：
- ANZ : number of points
- GST : field start (G)
- GSI : sweep increment / sweep width (G)
- HCF / HSW : center field / sweep width（fallback）
- MIN / MAX : data min / max（验证用）
- JDA / JTM : date / time（输出 ASC 第一行）

SPC 格式：1024 (或 ANZ) 个 little-endian IEEE float32（4 字节 / 点）。
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path


def parse_par(par_path: Path) -> dict:
    """
    解析 Bruker WinEPR .par 文本元数据文件。

    .par 是连续文本流（无换行分隔），字段格式为 `KEY value` 其中 KEY 通常 2-3 字符
    + 1 空格 + 值（可能含空格 / 小数 / 路径）。本函数提取常用字段。

    Returns
    -------
    dict with keys: ANZ (int), GST (float), GSI (float), HCF (float), HSW (float),
                    JDA (str), JTM (str), MIN (float), MAX (float)
    """
    text = par_path.read_text(encoding="utf-8", errors="replace")

    def find_num(key: str, default=None):
        # 匹配 KEY 后跟空格再跟数字（含负号 / 小数 / 科学记数法）
        m = re.search(rf"\b{re.escape(key)}\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", text)
        if not m:
            return default
        return float(m.group(1)) if "." in m.group(1) or "e" in m.group(1).lower() else int(m.group(1))

    def find_str(key: str, default=""):
        m = re.search(rf"\b{re.escape(key)}\s+(\S+)", text)
        return m.group(1) if m else default

    return {
        "ANZ": find_num("ANZ", 1024),
        "GST": find_num("GST"),
        "GSI": find_num("GSI"),
        "HCF": find_num("HCF"),
        "HSW": find_num("HSW"),
        "JDA": find_str("JDA"),
        "JTM": find_str("JTM"),
        "MIN": find_num("MIN"),
        "MAX": find_num("MAX"),
    }


def read_spc(spc_path: Path, n_points: int) -> list[float]:
    """
    读取 .spc 二进制文件（little-endian IEEE float32 数组）。

    Parameters
    ----------
    spc_path : Path to .spc
    n_points : expected number of points (from par ANZ)

    Returns
    -------
    list of float, length == n_points
    """
    raw = spc_path.read_bytes()
    expected_bytes = n_points * 4
    if len(raw) != expected_bytes:
        raise ValueError(
            f"SPC 文件大小不符：{spc_path.name} 是 {len(raw)} 字节，"
            f"按 ANZ={n_points} 预期 {expected_bytes} 字节（{n_points} × 4 byte float32）"
        )
    # little-endian float32
    return list(struct.unpack(f"<{n_points}f", raw))


def build_field_axis(par: dict) -> list[float]:
    """
    构造磁场轴 X [G]。

    优先用 GST + GSI（实际测量起始 + 扫宽），fallback HCF - HSW/2 + i × HSW/(ANZ-1)。

    每点间距：sweep / (ANZ - 1)，对应 ASC 中 X[0] = GST, X[ANZ-1] = GST + GSI。
    """
    anz = par["ANZ"]
    if par["GST"] is not None and par["GSI"] is not None:
        x0 = par["GST"]
        sweep = par["GSI"]
    elif par["HCF"] is not None and par["HSW"] is not None:
        x0 = par["HCF"] - par["HSW"] / 2.0
        sweep = par["HSW"]
    else:
        raise ValueError("PAR 缺关键字段：需要 GST+GSI 或 HCF+HSW")
    step = sweep / (anz - 1)
    return [x0 + i * step for i in range(anz)]


def write_asc(asc_path: Path, par_source_path: str, par: dict, x: list[float], y: list[float]) -> None:
    """
    输出 ASC 文件。格式：
    L1: Filename: <par 源路径>\t Date: YYYY-MM-DD   Time: HH:MM
    L2: 空行
    L3: X [G]\tIntensity
    L4..: <field>\t<intensity>
    末尾空行
    """
    lines = []
    lines.append(f"Filename:\t{par_source_path}\t Date: {par['JDA']}   Time: {par['JTM']}")
    lines.append("")
    lines.append("X [G]\tIntensity")
    for xi, yi in zip(x, y):
        lines.append(f"{xi:.6f}\t{yi:.6f}")
    lines.append("")
    lines.append("")
    asc_path.write_text("\n".join(lines), encoding="utf-8")


def convert_one(par_path: Path, asc_out: Path | None = None, par_source_override: str | None = None) -> Path:
    """
    转换单个 par → asc。

    Parameters
    ----------
    par_path : 工作区中 .par 路径
    asc_out  : 输出 asc 路径（默认与 par 同名 + .asc）
    par_source_override : ASC 第一行 Filename 字段的原始 par 路径
                          （默认用工作区 par 路径；如果想保留仪器机原路径可覆盖）

    Returns
    -------
    asc_out path
    """
    spc_path = par_path.with_suffix(".spc")
    if not spc_path.exists():
        raise FileNotFoundError(f"找不到同名 .spc：{spc_path}")

    par = parse_par(par_path)
    x = build_field_axis(par)
    y = read_spc(spc_path, par["ANZ"])

    if asc_out is None:
        asc_out = par_path.with_suffix(".asc")

    # 默认只记录文件名，避免把用户机器的绝对路径写进可分享结果。
    source = par_source_override or par_path.name
    write_asc(asc_out, source, par, x, y)
    return asc_out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("par_files", nargs="+", help=".par 文件路径（一个或多个）")
    ap.add_argument("-o", "--out", default=None, help="输出 .asc 路径（仅单文件时有效）")
    ap.add_argument("--source", default=None,
                    help="ASC 第一行 Filename 字段写什么（默认 = 输入 par 工作区路径）")
    ap.add_argument("--verify", default=None,
                    help="把生成的 ASC 与现有 ASC 文件对比（用于回归测试）")
    args = ap.parse_args()

    if args.out and len(args.par_files) > 1:
        print("ERROR: -o 仅在单文件模式下有效", file=sys.stderr)
        return 2

    out_paths = []
    for p_str in args.par_files:
        p = Path(p_str)
        if not p.exists():
            print(f"SKIP: 文件不存在 {p}", file=sys.stderr)
            continue
        try:
            asc_out = convert_one(
                p,
                asc_out=Path(args.out) if args.out else None,
                par_source_override=args.source,
            )
            out_paths.append(asc_out)
            print(f"OK: {p.name} → {asc_out.name}")
        except Exception as e:
            print(f"FAIL: {p.name} — {e}", file=sys.stderr)

    if args.verify and len(out_paths) == 1:
        verify_path = Path(args.verify)
        if verify_path.exists():
            ok, msg = verify_asc(out_paths[0], verify_path)
            print(f"VERIFY: {msg}")
            return 0 if ok else 3
        else:
            print(f"VERIFY 文件不存在：{verify_path}", file=sys.stderr)
            return 4

    return 0


def verify_asc(generated: Path, reference: Path, tol_rel: float = 1e-3) -> tuple[bool, str]:
    """
    比对生成的 ASC 与现有参考 ASC 的数据列（忽略头部 Filename 行，因路径可能不同）。

    返回 (is_match, message)
    """
    def parse_data(p: Path) -> list[tuple[float, float]]:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        # 找数据起始（X [G] 行的下一行）
        start = next((i + 1 for i, ln in enumerate(lines) if "X [G]" in ln), None)
        if start is None:
            return []
        data = []
        for ln in lines[start:]:
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.split()
            if len(parts) >= 2:
                try:
                    data.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
        return data

    g_data = parse_data(generated)
    r_data = parse_data(reference)
    if len(g_data) != len(r_data):
        return False, f"点数不符：生成 {len(g_data)} vs 参考 {len(r_data)}"

    max_rel_err = 0.0
    n_bad = 0
    for (gx, gy), (rx, ry) in zip(g_data, r_data):
        # 磁场轴严格匹配（容忍 0.01 G）
        if abs(gx - rx) > 0.01:
            return False, f"磁场轴不符：生成 {gx} vs 参考 {rx}"
        # 强度对比（相对误差）
        if abs(ry) > 1.0:
            rel = abs(gy - ry) / abs(ry)
            max_rel_err = max(max_rel_err, rel)
            if rel > tol_rel:
                n_bad += 1
    if n_bad == 0:
        return True, f"全部 {len(g_data)} 点强度匹配（最大相对误差 {max_rel_err:.2e}）"
    return False, f"{n_bad}/{len(g_data)} 点超过容忍 {tol_rel}；最大相对误差 {max_rel_err:.2e}"


if __name__ == "__main__":
    sys.exit(main())
