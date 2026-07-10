# scripts/

## 使用原则

写新脚本前先检查本目录。已有脚本可以满足任务时优先复用，避免临时脚本散落。

## 脚本

本目录保存当前项目专用的数据分析脚本。可跨项目复用、需要独立配置和安全说明的工具放在 `../tools/`。

真实论文使用 `../tools/objective-facts/` 中的正式版面解析与客观事实提取工具链；不再提供只支持自制 PDF 的玩具解析脚本。

### `analyze_activity.py`

使用 Python 标准库检查 CSV、计算 CO conversion、近似 T50 并生成 PNG 曲线。

```powershell
python scripts/analyze_activity.py data/raw/activity-run-001.csv data/processed
```

脚本不会修改输入文件。运行后仍需人工/AI 维护 README、日志和正式报告之间的关系。
