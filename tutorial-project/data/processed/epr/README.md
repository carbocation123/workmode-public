# processed/epr/

## 预生成结果

- `demo_epr.asc`：由 `data/raw/epr/demo_epr.par + demo_epr.spc` 转换得到的 1024 点两列文本谱。
- `demo_epr_scan.txt`：使用逐谱 MF = 9.8000 GHz、分析窗口 g 1.91–2.04、噪声窗口 g 1.94–1.955 的客观扫描输出。

## 复现

调用方式见 `tools/epr/README.md`。转换练习应输出为新文件 `demo_epr_user.asc`，再用 `--verify demo_epr.asc` 比较；不要覆盖预生成基准。

## 关键校验

- 点数：1024；
- B 轴：3100–3900 G；
- Signal A window pp / 3× noise = 20.02×；
- Signal B window pp / 3× noise = 4.76×。

这些数值只验证工具链和检测门限，不构成化学物种归属。
