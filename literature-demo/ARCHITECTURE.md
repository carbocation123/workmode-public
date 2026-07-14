# 文献特化 Workmode 架构

## 核心决策

文献库是固定结构的普通 Workmode 项目，不是独立 Agent 服务：

```text
正式 Workmode session/chat/context/compact/stop
                         │
             literature-project.json
                         │
 fixed project files ─ literature_* tools ─ literature UI
```

桌面根页面先提供应用级功能大厅；完整科研工作台与文献智库是同级入口，工作台本身不再重复文献导航。文献页面共享正式主题/签名皮肤基础，并通过 `literature-*` 与共享聊天语义槽位允许皮肤单独适配，不继承工作台专用布局；只有左侧 `activity-navigation` 与工作台使用相同结构和样式。文献设置按钮位于该活动栏底部，进入共享设置页并携带返回来源，不建立第二份配置状态；顶部不再放置重复导航、连接状态或特化模式徽章。

文献详情、项目笔记和项目记忆是从主网格定位规则中排除的居中 fixed 模态层，不改变 Workmode session。PDF 预览从 catalog 的 `paths.pdf` 映射到通用 `/fs/media`，并与完整工作台共同使用 `frontend/src/PdfViewer.tsx`；组件通过 Fetch 取得文件、创建 `blob:` URL、交给原生 PDF iframe，并在卸载时撤销 URL。文献投影不维护第二个 PDF 查看器，也不把可被下载软件接管的 HTTP PDF 地址直接交给 iframe。

旧纵切后端曾维护独立 store、session、chat loop、compactor、任务和两阶段写入。它已经退出 FastAPI 导入路径并归档到 `archive/standalone-backend-2026-07-13/`，只用于历史对照。

## 前端到权威来源映射

| 前端区域 | 正式来源 |
|---|---|
| 项目身份 | Workmode 项目注册记录 + `literature-project.json` |
| session 下拉框 | `data/work/sessions/<project-slug>/*.meta.json` |
| 对话与工具卡 | 同目录 JSONL；正式 `TurnRecorder` 事件 |
| 上下文与压缩 | 正式 context/compact API |
| 停止生成 | 正式 chat run cancellation |
| 文献列表和详情概览 | `catalog.json` |
| 标签分类筛选 | `tags.json` + `catalog.json.tag_ids` |
| 原始 PDF | `catalog.paths.pdf` + 受控媒体端点 |
| MinerU 正文 | `catalog.paths.full_md` |
| 完整客观事实 | `catalog.paths.fact_report` |
| 笔记 | `notes/*.md` |
| 已处理索引 | `processed-index.md` |
| 项目协议 | `WORKMODE.md` → `@LITERATURE_PROJECT.md` |
| 项目记忆 | 正式 Workmode project memory |

前端完成领域写操作或聊天工具轮次后重新读取这些来源；工具返回对象只用于显示本次结果，不成为第二份永久状态。

PDF 拖拽先停留在前端确认弹窗，不直接写盘。确认上传完成后，前端把真实 paper ID 批次提交给当前正式 session；后端写入 `meta.event=literature_import_confirmed` 的 system 事件。该事件在聊天时间线中隐藏，Prompt 构建时根据 paper ID 重新读取 catalog 并生成 `<LITERATURE_IMPORT_EVENT>`，明确告诉模型论文已经注册、不要再次索要路径，并在用户说“继续”时使用 `literature_process`。压缩器会把较早的系统事件纳入摘要，原始 JSONL 仍保留。

## 工具画像

`project_tool_schemas(project_slug)` 读取项目 manifest。文献项目只发送：

```text
literature_search
literature_tag_list
literature_read
literature_import
literature_process
literature_update_record
literature_update_cross_relation
literature_archive
literature_note_search
literature_note_read
literature_note_upsert
literature_note_export
```

Shell、Python、通用 read/write/edit/glob/grep、Web、通用 memory 和 plan schema 不进入模型请求。写工具是直接领域命令，不使用 proposal/confirm/reject。后端只做确定性身份、路径、schema、引用、冲突和原子写入校验。

`literature_tag_list` 是标签写入前的只读注册表入口，返回规范 ID、名称、别名、分类、状态和使用次数。`literature_update_record` 应优先复用查询到的规范名称或别名；只有注册表中不存在同义概念时才创建 provisional 标签。

## 当前资料

界面勾选文献或笔记后，下一条用户消息携带：

```json
{
  "content": "比较这两篇文章",
  "active_context": [
    {"kind": "paper", "id": "paper-id"},
    {"kind": "note", "id": "discussion.md"}
  ]
}
```

该数组原样写入用户消息 `meta.active_context`。Prompt 构建器附加轻量记录和真实存在状态，模型需要长正文时调用 `literature_read`。选择只影响优先上下文；领域工具可处理当前项目中任意真实 ID。

## MinerU 与事实报告

`literature_process` 是同步工具：一次调用内完成 MinerU、元数据和事实报告，不建立第二套任务存储。流水线产物固定为：

```text
papers/unprocessed/extracted/<paper-id>/
  full.md
  layout.json
  *_content_list.json
  images/
  objective-facts.md
```

报告固定六段，前五段只写客观事实，第六段保留给主对话。关键数值和作者观点必须携带基于 `page_idx` 的位置。元数据不足时流水线失败并保留诊断，不从原文件名猜测。工具停止事件会传入流水线，轮询和下载块之间检查取消。

## 结构保护

- 初始化器只补齐缺失的固定文件，不覆盖已有内容；
- PDF 按 SHA-256 去重，碰撞不覆盖；
- catalog/tags 使用同目录临时文件和 `os.replace`；
- 通用 Markdown 编辑器只允许既有 `notes/*.md`；
- 归档前验证 PDF、`full.md`、事实报告、元数据、标准名和第六段；
- 归档在移动任何文件前预检 PDF 与解析目录的全部目标位置；通过后更新 catalog 全部相对路径并重建 `processed-index.md`；
- 前端或 session 旧文字与项目文件冲突时，以重新读取的项目文件为准。

## 尚未完成

真实 MinerU 联网验收、DOI 语义去重、标签治理和最终主档生成仍在后续阶段。文献页面已经迁入 `frontend/src/literature/`，由主 Vite 工程生成 `/literature/` 并随正式桌面 `frontend/dist` 打包；旧 5176 开发壳已归档。项目标题和上下文占用来自正式 Workmode API；旧 Demo 的静态标题、假百分比和独立任务轮询已经移除。
