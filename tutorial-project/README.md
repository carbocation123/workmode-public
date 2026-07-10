# 催化科研协作教程

> **AI 教学入口：**这是主持式演示项目。收到“开始”后，先读 `TUTORIAL_AI_GUIDE.md` 和 `notes/demo-state.md`；一次用户回复只演示一个单元。工作不是目的，演示才是目的。

## 项目说明

这是 Workmode Public 的教学项目。研究故事是：比较三种不同焙烧温度制备的虚构氧化物催化剂，判断焙烧温度是否影响 CO 氧化活性；同时用一篇真实论文独立练习可追溯的客观事实提取。

全部内容只用于教学：

- 样品 C300、C450、C600 为虚构样品；
- `papers/s41467-019-13638-9.pdf` 是真实开放获取论文，依据 CC BY 4.0 随教学项目分发，不属于本项目成果；
- 仪器 CSV 是合成数据；
- 真实论文中的内容属于原作者；虚构样品和合成数据不代表任何真实课题、实验结果或科学结论。

## 项目主干

```text
START_HERE.md                 用户入口
WORKMODE.md                   本项目专属提示词入口（自动固定注入）
WORKMODE_TUTORIAL.json        官方教程标识与模板版本（用于安全重置）
INSTRUCTIONS.md               科研协作与文件系统纪律
TUTORIAL_AI_GUIDE.md          AI 教学流程和完成条件
manuscript/                   文章草稿与润色
papers/                       文献、下载队列与提取结果
experiments/                  研究问题、仪器条件和实验计划
data/raw/                     不可修改的模拟 CSV 与 EPR PAR/SPC 原始数据
data/processed/               派生数据输出
notes/                        实验日志和教程进度
reports/                      正式分析报告
scripts/                      可复现的项目脚本
tools/                        可复用工具及其配置说明
```

## 权威关系

- 项目结构以本 README 与硬盘实际目录共同为准；两者不一致时必须报告。
- 项目级教学行为由 `WORKMODE.md` 固定注入，只作用于本项目，不写入基础提示词或工作记忆。
- `WORKMODE_TUTORIAL.json` 与应用创建时写入的本地注册记录共同识别官方教程；只复制标识文件不会获得「重置教程」权限。
- 通用协作纪律以 `INSTRUCTIONS.md` 为准。
- 教程顺序与完成条件以 `TUTORIAL_AI_GUIDE.md` 为准。
- 主持式对话的当前单元以 `notes/demo-state.md` 为准；项目成果是否存在以 `notes/tutorial-progress.md` 为准，两者不得混用。
- 仪器原始记录以 `data/raw/` 为准，不允许修改。
- 研究问题以 `experiments/research-question.md` 为准。
- 文献客观事实工具以 `tools/objective-facts/README.md` 为准。
- 教程主持进度以 `notes/demo-state.md` 为准。

## 数据链

```text
papers/s41467-019-13638-9.pdf（真实开放获取文献）
  -> tools/objective-facts/pdf2md.py
  -> papers/extracted/s41467-019-13638-9/full.md
  -> tools/objective-facts/prep_paper_for_deepseek.py
  -> papers/extracted/s41467-019-13638-9/s41467-019-13638-9_prepared.txt
  -> tools/objective-facts/deepseek_batch.py
  -> papers/extracted/s41467-019-13638-9/s41467-019-13638-9_客观事实抽取报告_v2.md

experiments/research-question.md（虚构教学问题）
  -> experiments/plan.md

data/raw/activity-run-001.csv
  -> data/processed/activity-processed.csv
  -> data/processed/activity-summary.md
  -> reports/activity-analysis.md
  -> manuscript/introduction.md（只在证据支持时修改科学表述）

data/raw/epr/demo_epr.par + demo_epr.spc（明确标记为模拟）
  -> tools/epr/bruker_spc2asc.py
  -> data/processed/epr/demo_epr.asc
  -> tools/epr/epr_scan.py
  -> data/processed/epr/demo_epr_scan.txt
  -> reports/epr-demo-analysis.md
```

真实文献链与虚构实验链默认相互独立。除非用户明确确认相关性并且原文证据足够，不得把真实论文中的结论迁移成虚构实验的结论。

结构、路径或成果归宿发生变化时，必须同步维护这条关系和相应目录 README。
