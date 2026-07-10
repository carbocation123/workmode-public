# epr/

## 用途

演示无需 Bruker WinEPR 软件时，如何把 `.par + .spc` 二进制原始谱转换为可审计的 `.asc`，再计算逐谱 g 轴、峰峰值和噪声门限。

## 工具

- `bruker_spc2asc.py`：读取 PAR 元数据和 little-endian float32 SPC，生成两列 ASC。
- `epr_scan.py`：读取 ASC 与同名 PAR，用该谱自己的微波频率换算 g 轴，报告窗口峰峰值和 3× 噪声门限。
- `generate_demo_epr.py`：只用于重建教程中的确定性模拟谱；不是仪器文件生成器。

全部脚本只依赖 Python 标准库。

## 教程数据

```text
data/raw/epr/demo_epr.par
data/raw/epr/demo_epr.spc
  -> bruker_spc2asc.py
  -> data/processed/epr/demo_epr.asc
  -> epr_scan.py
  -> data/processed/epr/demo_epr_scan.txt
  -> reports/epr-demo-analysis.md
```

原始文件和预生成结果都随项目提供。用户在教程中运行转换后，应先与预生成 ASC 比较，再讨论结果。

## Workmode Public 调用

转换：

```json
{
  "tool": "project_python_file",
  "path": "tools/epr/bruker_spc2asc.py",
  "args": [
    "data/raw/epr/demo_epr.par",
    "-o",
    "data/processed/epr/demo_epr_user.asc",
    "--source",
    "data/raw/epr/demo_epr.par",
    "--verify",
    "data/processed/epr/demo_epr.asc"
  ]
}
```

客观扫描：

```json
{
  "tool": "project_python_file",
  "path": "tools/epr/epr_scan.py",
  "args": [
    "data/processed/epr/demo_epr.asc",
    "--par",
    "data/raw/epr/demo_epr.par",
    "--noise-window",
    "1.94",
    "1.955"
  ]
}
```

## 科研边界

- 文件内明确写有 `SIMULATED TRUE`，不能改称实测数据。
- Signal A / Signal B 的 g 值是生成参数，不代表任何真实物种。
- 3× 噪声只表示检测门限；出现完整正负瓣也不等于化学归属成立。
- 真实谱分析必须保留原始 PAR/SPC、逐谱微波频率、处理条件和独立表征证据。
