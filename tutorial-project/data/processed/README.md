# processed/

## 用途

保存由项目脚本或工具从 raw 数据生成的可再生结果。

预期输出：

- `activity-processed.csv`：逐点 conversion；
- `activity-summary.md`：质量检查与近似 T50；
- `conversion-curves.png`：教学曲线图。
- `epr/demo_epr.asc`：由模拟 PAR/SPC 转换的预生成两列谱；
- `epr/demo_epr_scan.txt`：逐谱 g 轴与噪声门限的预生成客观扫描摘录。

生成后必须登记输入、工具、参数和输出时间，并同步更新 `data/raw/README.md` 的下游去向。EPR 详细关系见 `epr/README.md`。
