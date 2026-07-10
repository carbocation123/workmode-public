# objective-facts/

## 用途

把真实 PDF 转成可追溯的六段式客观事实报告：

```text
PDF
  -> pdf2md.py / MinerU 版面解析
  -> prep_paper_for_deepseek.py / 页码化模型输入
  -> deepseek_batch.py + prompts/literature_summary_6sections.txt
  -> *_客观事实抽取报告_v2.md + batch_manifest.json
```

`run_pipeline.py` 把三步串起来。全部脚本只依赖 Python 标准库。

## 安全边界

- `pdf2md.py` 会把原始 PDF 上传到 MinerU，必须显式传入 `--yes-upload`。
- `deepseek_batch.py` 会把页码化文献文本发给模型服务，必须显式传入 `--yes-send`。
- `run_pipeline.py` 分别要求 `--allow-mineru-upload` 和 `--allow-model-send`。
- `--dry-run` 不读取密钥、不访问网络，可先检查路径与计划。
- 不把 `.env`、`mineru_config.json` 或 `deepseek_config.json` 提交、分享或写入报告。

开放获取不等于无需确认外传；许可解决的是使用和再分发权，不替代用户对第三方上传的授权。

## 初次配置

在本目录中：

1. 复制 `mineru_config.example.json` 为 `mineru_config.json`，仅在本机填写 MinerU key；也可设置环境变量 `MINERU_API_KEY`。
2. 在 Workmode Public 中已经配置的模型 API 会自动复用；无需把模型 key 再写入项目。开发者独立运行脚本时，也可复制 `deepseek_config.example.json` 或设置 `MODEL_API_KEY`。
3. 模型接口默认使用 DeepSeek Chat Completions；可通过 `MODEL_ENDPOINT` 和 `MODEL_NAME` 指向其它兼容接口。

配置文件已被本目录 `.gitignore` 排除。

## 教程论文

本教程**不调用外部服务**。它只让 AI 用内置 Python 做 dry-run，向用户解释真实运行需要的配置、传输对象和输出位置：

```json
{
  "tool": "project_python_file",
  "path": "tools/objective-facts/run_pipeline.py",
  "args": ["papers/s41467-019-13638-9.pdf", "--dry-run"]
}
```

随项目已经提供：

- 代表性的 `*_content_list.json` 和 `full.md` 版面解析快照；
- 由真实预处理脚本生成、且头部标记 `Tutorial precomputed snapshot (no API call)` 的 `*_prepared.txt`；
- 六段式客观事实报告示例；
- 明确标记 `network_calls: 0` 的教学 manifest。

位置：`papers/extracted/s41467-019-13638-9/`。快照只包含代表性结构块，不冒充完整 MinerU 输出。

## 正式项目运行

若用户在自己的正式项目中确实要重新处理 PDF，需要先配置 MinerU key，并确保 Workmode Public 已配置模型 API。用户理解并分别明确同意两次外部传输后，才运行：

```json
{
  "tool": "project_python_file",
  "path": "tools/objective-facts/run_pipeline.py",
  "args": [
    "papers/s41467-019-13638-9.pdf",
    "--allow-mineru-upload",
    "--allow-model-send"
  ],
  "timeout": 300
}
```

默认输出到 `papers/extracted/<pdf-stem>/`。本教程不执行这条联网命令。

`project_python_file` 使用软件安装包自带的 Python，因此用户不需要另外安装 Python。下面的分步命令只用于开发者终端或已有 Python 环境的人工排障。

## 开发者分步运行

```powershell
python tools/objective-facts/pdf2md.py papers/s41467-019-13638-9.pdf `
  --output-dir papers/extracted/s41467-019-13638-9 `
  --yes-upload

python tools/objective-facts/prep_paper_for_deepseek.py `
  papers/extracted/s41467-019-13638-9 `
  -o papers/extracted/s41467-019-13638-9/s41467-019-13638-9_prepared.txt

python tools/objective-facts/deepseek_batch.py `
  --prompt-file tools/objective-facts/prompts/literature_summary_6sections.txt `
  --inputs papers/extracted/s41467-019-13638-9/s41467-019-13638-9_prepared.txt `
  --output-dir papers/extracted/s41467-019-13638-9 `
  --output-suffix _客观事实抽取报告_v2.md `
  --model deepseek-v4-pro `
  --concurrency 1 `
  --yes-send
```

正式报告完成后仍需由主对话复核页码、Figure/Table 定位和事实归属；第 6 节由主对话在用户参与下填写。
