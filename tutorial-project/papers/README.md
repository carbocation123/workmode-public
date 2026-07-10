# papers/

## 用途

保存文献候选、人工下载的 PDF 和可追溯提取结果。

## 当前内容

- `s41467-019-13638-9.pdf`：真实 Nature Communications 开放获取论文，依据 CC BY 4.0 随教程分发。
- `s41467-019-13638-9.md`：题录、DOI、来源、许可证和归属说明。
- `download_queue.md`：网络调研后交给用户人工下载的候选清单；初始状态只登记随教程提供的真实论文，其他候选由演示过程补充。
- `extracted/`：PDF 文本与客观事实报告的输出位置。
  - `extracted/s41467-019-13638-9/`：离线预计算教学快照、页码化输入、六段式报告和 manifest；未进行外部调用。

## 工作流

```text
web_search/web_fetch
  -> download_queue.md
  -> 用户人工下载 PDF
  -> tools/objective-facts/pdf2md.py / PDF 版面解析
  -> tools/objective-facts/prep_paper_for_deepseek.py / 带印刷页码的模型输入
  -> tools/objective-facts/deepseek_batch.py / 六段式客观事实报告
  -> 人工判断是否可进入实验规划/文章引用
```

教程只运行 dry-run 并检查预计算结果，不真正调用 MinerU 或模型 API。搜索摘要不能直接进入客观事实报告；每篇已处理 PDF 都应在本 README 登记提取结果的位置和实际/模拟状态。

## 再分发与归属

`s41467-019-13638-9.pdf` 的 PDF 正文和出版页面均声明采用 Creative Commons Attribution 4.0 International License。教程可以保留并分发未经修改的原始 PDF，但必须署名作者和来源、链接许可证并注明是否修改。带有单独版权说明的第三方图像或材料不得脱离原论文另行提取、改编或复用，除非相应权利允许。
