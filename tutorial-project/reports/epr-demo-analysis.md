# 模拟 EPR 工具链报告

## 来源与身份

- 原始模拟元数据：[`data/raw/epr/demo_epr.par`](../data/raw/epr/demo_epr.par)
- 原始模拟二进制：[`data/raw/epr/demo_epr.spc`](../data/raw/epr/demo_epr.spc)
- 生成记录：[`data/raw/epr/demo_epr_generation.json`](../data/raw/epr/demo_epr_generation.json)
- 转换工具：`tools/epr/bruker_spc2asc.py`
- 扫描工具：`tools/epr/epr_scan.py`
- 派生 ASC：[`data/processed/epr/demo_epr.asc`](../data/processed/epr/demo_epr.asc)
- 客观扫描：[`data/processed/epr/demo_epr_scan.txt`](../data/processed/epr/demo_epr_scan.txt)

所有输入均为教学模拟，不是仪器实测或真实样品。

## 可复现观察

1. SPC 文件大小为 4096 bytes，与 PAR 中 `ANZ 1024` 和 float32 的 4 bytes/point 一致。
2. 转换后 ASC 有 1024 个数据点，B 轴为 3100–3900 G。
3. 按该谱自己的 MF = 9.8000 GHz 换算 g 轴；不能借用其它谱的平均微波频率。
4. 噪声窗口 g 1.94–1.955 的 pp 为 2.818e-02，3× 门限为 8.454e-02。
5. Signal A 窗口 pp 为 1.693e+00，约为门限 20.02 倍；Signal B 窗口 pp 为 4.021e-01，约为门限 4.76 倍。

## 不能推出的内容

- 不能把 Signal A 或 Signal B 自动归属为氧空位、自由基、Ce³⁺、Mn²⁺或其它物种；
- 不能从模拟谱推出真实材料、处理气氛或反应机理；
- “高于 3× 噪声”只表示在本模拟和指定噪声窗口下可检测，不表示归属正确。

## 教学要点

AI 的职责是保留原始文件、使用逐谱 MF、报告参数和检测门限，并把观察与归属分开。用户负责决定真实研究中还需要哪些对照、处理链和独立表征证据。
