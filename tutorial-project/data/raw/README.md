# raw/

## 保护规则

本目录模拟仪器源头数据区。文件不可修改、覆盖、删除或重命名。

## 原始文件登记

| 文件 | 来源 | 已知质量问题 | 下游结果 |
|---|---|---|---|
| `activity-run-001.csv` | 教学在线 CO 分析器导出 | 1 条缺失出口浓度；1 条完全重复记录 | 尚未生成 |
| `epr/demo_epr.par` + `epr/demo_epr.spc` | `tools/epr/generate_demo_epr.py` 确定性生成；明确标记为模拟 | 非实测数据；Signal A/B 为生成参数，不能做化学归属 | `data/processed/epr/demo_epr.asc`、`demo_epr_scan.txt`、`reports/epr-demo-analysis.md` |

分析完成后，只更新本 README 的「下游结果」字段，不修改 CSV。
