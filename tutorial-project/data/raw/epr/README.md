# raw/epr/

## 内容

- `demo_epr.par`：Bruker 风格文本元数据，明确含 `SIMULATED TRUE`。
- `demo_epr.spc`：1024 个 little-endian IEEE float32 强度点，共 4096 bytes。
- `demo_epr_generation.json`：生成参数、固定随机种子和文件 SHA-256。

## 模拟设计

- 磁场范围：3100–3900 G；
- 微波频率：9.8000 GHz；
- 模拟测温：77 K；
- Signal A：生成参数 g = 2.003；
- Signal B：生成参数 g = 1.965；
- 叠加确定性基线与固定随机种子噪声。

这些文件不是仪器实测数据，不允许更名或描述成真实样品。原始模拟文件保持只读；如需重建，在临时目录运行 `tools/epr/generate_demo_epr.py` 并比较 manifest 哈希，不覆盖本目录。

## 下游

```text
demo_epr.par + demo_epr.spc
  -> tools/epr/bruker_spc2asc.py
  -> data/processed/epr/demo_epr.asc
  -> tools/epr/epr_scan.py
  -> data/processed/epr/demo_epr_scan.txt
  -> reports/epr-demo-analysis.md
```
