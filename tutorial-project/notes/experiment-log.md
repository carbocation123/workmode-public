# 教学实验日志

## 2026-01-15 至 2026-01-17：合成活性评价

- 样品：C300、C450、C600（均为教学模拟）
- 研究问题：[experiments/research-question.md](../experiments/research-question.md)
- 仪器条件：[experiments/instrument-profile.md](../experiments/instrument-profile.md)
- 原始数据：[data/raw/activity-run-001.csv](../data/raw/activity-run-001.csv)
- 数据质量：已知包含一条缺失信号和一条重复记录
- 数据归宿：尚未生成 processed 结果与正式报告

## 2026-07-10：模拟 EPR 文件工具链

- 身份：确定性生成的教学模拟谱，不是真实仪器数据或真实样品
- 原始格式：Bruker 风格 `demo_epr.par + demo_epr.spc`
- 原始数据：[data/raw/epr/README.md](../data/raw/epr/README.md)
- 转换工具：[tools/epr/README.md](../tools/epr/README.md)
- 预生成结果：[data/processed/epr/README.md](../data/processed/epr/README.md)
- 正式教学报告：[reports/epr-demo-analysis.md](../reports/epr-demo-analysis.md)
- 边界：3× 噪声和完整正负瓣只用于检测与谱形检查，不做化学物种归属
