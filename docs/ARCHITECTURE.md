# Workmode Public 架构

本文描述当前 `main` 分支和正式桌面发行版的真实实现。历史便携包只作为数据迁移来源，不再属于当前运行架构。

## 设计目标

Workmode Public 是本地优先的科研工作助手：

- 以用户明确注册的本地项目为权限和数据边界；
- 保存完整、可追踪的会话和工具事件；
- 按 token 预算构建模型上下文，而不是把整个 session 无条件发送给模型；
- 固定加载项目协议、工作记忆和任务计划；
- 不加载伴侣人格、生活记忆或私人关系模块；
- 桌面版把应用文件与用户数据分离，支持签名更新。

## 运行拓扑

正式 Windows 桌面版由三个部分组成：

```text
Tauri 2 desktop process
  ├─ 启动捆绑的 Python/FastAPI 后端（动态 loopback 端口）
  ├─ 等待 /api/health
  ├─ 把 API base 交给 React 前端
  └─ 关闭、更新或退出时终止后端进程树

React/Vite frontend
  └─ 通过 /api 与本地 FastAPI 通信

FastAPI backend
  ├─ 文件型项目、会话和工作状态存储
  ├─ OpenAI-compatible 模型流
  └─ 项目工具与公开网页工具执行器
```

源码开发可以不用 Tauri：Vite 运行在 `127.0.0.1:5173`，FastAPI 默认运行在 `127.0.0.1:8765`。

## 后端模块

入口是 `backend/app/main.py`。

- `config.py`：环境变量、模型设置、数据目录、静态目录和允许的前端来源。
- `storage.py`：项目、活动项目、session 元数据、JSONL 消息和项目工作记忆。项目/会话移除采用软删除。
- `routes.py`：`/api` 健康检查、设置、项目、会话、上下文、文件和流式聊天接口。
- `chat_runs.py`：按 session 维护正在运行的任务与取消事件。
- `prompt.py`：中性科研助手 system prompt、固定上下文和模型消息构建。
- `context_imports.py`：展开项目工作记忆中的 `@相对路径` 引用。
- `context_window.py`：从 token 预算中选择最近合法历史后缀。
- `session_compactor.py`：生成手动压缩摘要并插入续接标记，不删除历史。
- `llm.py`：OpenAI-compatible 流式请求和无固定轮数上限的工具循环。
- `turn_recorder.py`：按实际流式顺序持久化助手文字、工具开始和工具结果。
- `history_repair.py`：启动时修复旧版本留下的悬空工具开始事件，并先做原子备份。
- `files.py`：项目文件树、UTF-8 文本、Markdown 写回和 PDF/图片白名单预览。
- `project_tools.py`：项目文件、搜索、命令、网页和工作状态工具的 schema 与统一分发。
- `web_tools.py`：并行网页搜索/抓取、正文提取、响应限制与 SSRF 防护。
- `work_state.py`：项目/全局结构化记忆和当前任务计划。
- `tutorial_project.py`：官方教程标识、安装、重置、备份和新会话切换。
- `literature_project.py`、`endnote_import.py`、`literature_pipeline.py`、`literature_routes.py`：正式 Workmode 的文献项目识别、固定结构策略、EndNote 只读迁移、16 个领域工具、MinerU/事实抽取和文献前端投影 API；不复制 session、聊天循环、上下文或压缩器。
- `transcription/`：无 session 的会议录音文件工具。`workspace.py` 只管理固定 `tools/input/output` 目录、单工作线程、任务恢复、AI 派生文件和成对回收；`dashscope_fun_asr.py` 适配 Files API、Fun-ASR 异步轮询、说话人分段和结果下载；`ai_processing.py` 复用共享 OpenAI-compatible 模型设置，执行忠实润色与分段汇总；`routes.py` 提供上传、列表、结果、重试、改名、AI 生成/读取/清除、下载、删除与恢复 API。
- `writing/`：无 session 的文章处理工具。`skill_loader.py` 从版本化 `@.../SKILL.md` 清单展开纯文本处理规则；`processing.py` 执行忠实润色、长文分块核查、全篇合并和明确 Unicode 上下标/下标规范化；`history.py` 管理不可变成功记录与可恢复删除；`routes.py` 提供状态、处理、轻量历史列表、全文详情、删除与恢复 API。
- `pdf_text.py`：受大小、页数和字符数约束的本地 PDF 文本层抽取；不执行 OCR，不调用外部服务，供文献全文读取在 MinerU Markdown 缺失时降级使用。

`POST /api/settings/model/test` 接受尚未保存的 Base URL、模型名和可选 API Key，执行一个最多 8 token 的非流式 Chat Completions 探测。草稿不会写入 `.env`；前端只在探测成功后调用既有设置保存接口。后端把认证、地址/模型不存在、限流/余额、上游故障、超时和非兼容 JSON 转成面向普通用户的错误说明，不回显 API Key 或上游正文。

## 本地数据模型

桌面壳显式设置 `WORKMODE_PUBLIC_DATA_DIR=%LOCALAPPDATA%\WorkmodePublic\data`，配置文件和日志位于同一应用根目录的其他子目录：

```text
%LOCALAPPDATA%\WorkmodePublic\
  config\.env
  data\
    work\
      active.json
      projects\<project-slug>.json
      sessions\<project-slug>\<session-id>.meta.json
      sessions\<project-slug>\<session-id>.jsonl
      memory\global.md
      memory\projects\<project-slug>.md
      state\memory\...
      state\plans\<project-slug>.json
      tutorial-projects\<project-slug>.json
      tutorial-backups\<project-slug>\<reset-id>\
        project-files\
        project-memory.md
        work-state\
    article-processing\
      history\<record-id>.json
      .trash\<trash-id>.json
    backups\history-repair\
  logs\
    runs\<run-id>\
      manifest.json
      desktop.log
      frontend.log
      backend.out.log
      backend.err.log
  reports\
```

直接运行后端时，若未设置覆盖变量，Windows 默认数据目录是 `%APPDATA%\WorkmodePublic`，其他系统是 `~/.workmode-public`。

会议转写文件不进入 session 数据目录。默认工作区为 `D:\workmode\meeting-transcription`（没有 D 盘时为 `~/workmode/meeting-transcription`，可用 `WORKMODE_TRANSCRIPTION_DIR` 覆盖）：

```text
meeting-transcription\
  tools\README.md
  input\<任务 ID>\recording.<扩展名>
  output\<任务 ID>\
    meta.json
    asr-result.json
    transcript.json
    transcript.md
    transcript.txt
    ai-polished.md       用户手动生成时存在
    ai-summary.md        用户手动生成时存在
    ai-meta.json         AI 模型、生成时间与源文本指纹；不含密钥
  output\.trash\<回收 ID>\
```

任务列表只允许扫描 `output/<任务 ID>/meta.json`，不遍历根目录其它内容。Fun-ASR 签名 URL 不落盘；`meta.json` 保存固定模型名、远端 task ID、状态、错误与相对路径，后端重启时据此恢复 `queued/transcribing` 任务。AI 润色/总结只有在转写完成后才能手动触发，原始 `transcript.*` 和 `asr-result.json` 永不被 AI 写回。长总结采用“分段摘要 → 最终合并”，所有提示都要求缺失信息写为“未明确提及”而不是补写；保存前比较原文 SHA-256，模型运行期间若原文发生变化则丢弃旧结果。重新转写完成后移除旧 AI 文件，未完成状态也拒绝下载旧结果。删除把同 ID 的输入和输出作为一个单位移入 `output/.trash`，恢复前同时检查两个原目标，绝不覆盖。若用户以后把该根目录注册到通用工作台，新增的项目说明、笔记和会话都不会进入转写状态；会话仍由 `storage.py` 保存在应用数据目录。

文章处理不绑定项目目录。每次成功调用把原始输入、模式、输出、模型、时间和字数写成单独 JSON；失败请求不伪造成功记录。历史列表只投影 ID、时间、模式、模型、字数和 80 字预览，选中记录后才读取全文。删除把整条记录移入 `.trash`，恢复前检查原 ID 不存在，绝不覆盖。该数据不进入 Workmode session、JSONL、上下文压缩或项目记忆。

项目记录只保存路径、显示信息和父项目关系，不复制用户项目。移除项目只归档注册记录，硬盘文件不受影响。会话消息是 append-only JSONL；删除会话只在元数据写入 `deleted_at`。

官方教程是例外的显式复制流程：`tutorial-project/` 在构建时进入桌面资源，用户点击「创建教程项目」后才复制到其选择的目录。教程身份由项目内 `WORKMODE_TUTORIAL.json` 与应用数据中的 slug/root 注册记录共同确认；复制标识到普通项目不能获得重置权限。重置先备份文件和项目状态，再恢复内置模板并软删除旧会话。

## 请求与上下文流

一轮模型请求的上下文装配顺序是：

```text
中性 system 规则
  + 当前项目元数据
  + WORKMODE.md 项目级提示词及其 @文件展开结果
  + 全局/项目工作记忆
  + @项目文件展开结果与警告
  + 结构化记忆索引和正文
  + 当前任务计划
  + 全部必要工具 schema
  + token 预算允许的最近会话后缀
```

具体流程：

1. `prompt.build_system_prompt` 组合固定部分并估算 token；
2. `session_compactor.messages_visible_to_llm` 从最新 `<CONTEXT_SUMMARY>` 标记确定可见历史起点；
3. `_history_to_openai_messages` 把 JSONL 工具事件重建为 OpenAI-compatible `tool_calls` 和 `tool` 消息；
4. `context_window.build_context_window` 扣除 system 与工具 schema 后，从最近历史向前装入合法后缀；
5. 选中后缀必须从 user/system 消息开始，避免孤立工具结果；
6. 使用情况通过上下文接口和 SSE 事件返回前端 token 条。

估算器用于装载决策和 UI 指示，不等同于模型供应商账单中的精确 tokenizer 计数。

### 固定导入

`@relative/file.md` 必须单独占一行，路径相对当前项目根目录。实现只接受项目内 UTF-8 文本，限制递归深度并检测循环引用。导入失败会作为可见警告进入 prompt 和上下文状态。

### 项目级提示词

若项目根目录存在 `WORKMODE.md`，`prompt.build_system_prompt` 会先读取并展开其中的 `@相对路径`，再以“仅当前项目”的独立 system prompt 段注入。它不写入基础 `SYSTEM_BASE`，也不依赖应用数据目录中的工作记忆，因此协议可随项目复制和分发。缺少该文件的项目不会出现这一段；读取失败、越界、非 UTF-8、二进制和循环引用会进入上下文警告。token 状态分别记录入口正文、展开总量和导入文件。

### 工作记忆

项目工作记忆文本、结构化项目/全局记忆的索引和正文、当前计划都固定注入。结构化记忆正文共享工作状态上下文的长度保护；需要刷新或逐字确认时模型仍可调用 `memory_read`。

### 压缩

`POST /api/work/sessions/{id}/compact` 使用八段摘要结构写入一个 system marker：主要请求、关键概念、文件与代码、错误与修复、解决过程、用户消息、待办和下一步。原始 JSONL 不被删除；重复压缩以最新 marker 作为下一次续接边界。

## 工具循环与持久化顺序

模型直接获得所有必要工具 schema，不使用动态工具搜索。`llm.py` 的循环没有固定轮数上限：模型返回工具调用后，后端执行工具、把结果放回模型消息，然后继续请求，直到出现最终正文、用户取消或无法继续的模型/网络错误。普通工具失败以 `ok=false` 和错误正文返回模型，不会单独触发固定轮次终止。

流式事件包括：

- 助手 `delta`；
- `tool_call_start`；
- `tool_result`；
- `loop_continue`；
- 上下文、完成、停止或错误事件。

`TurnRecorder` 在每次工具开始前先刷出已经生成的助手文字，因此持久化回放仍保持用户看到的“文字 → 工具 → 文字”顺序。停止时：

- 上游 HTTP 流和后续工具轮次被取消；
- shell/Python 收到取消事件并终止进程树；
- 部分助手文字带 `meta.interrupted=true` 保存；
- 已开始但未返回的工具写入 `status=cancelled` 的结果；
- 若完全没有助手文字，会写入小型 `generation_stopped` 标记。

启动迁移会为旧版悬空 `tool_call_start` 插入已取消结果。修改前先把原 JSONL 和 session 元数据备份到 `data/backups/history-repair/<batch>/`；迁移可重复运行，不改写已有成功/失败结果，也不猜测旧版本未保存的文字边界。

## 项目工具边界

文件工具将路径解析到活动项目根目录并拒绝绝对路径、`..` 越界、依赖/缓存目录和敏感配置。读取支持行范围；写入和结果有大小限制。

`project_bash` 和 `project_python` 在项目根目录运行命令或内联代码。`project_python_file` 使用当前后端的 `sys.executable` 直接运行项目内已有 `.py` 文件，因此桌面安装版复用内置 Python，不依赖系统 Python 或 shell PATH。三者具有超时、输出截断和取消能力；shell 命令另有破坏性命令黑名单，但都不提供容器或 OS 级隔离。

`web_search` 最多并行处理 5 个 query，每个最多返回 8 条。默认检索源是 `html.duckduckgo.com/html/`：免 API Key，以 HTML 结果卡解析标题、摘要和链接，并把 DuckDuckGo 的 `uddg` 跳转地址还原为原始公开网页；结果载荷明确标记 `engine=duckduckgo-html`。该来源的连通性取决于用户网络环境，失败时按 query 返回网络错误，不伪装成空结果或本地能力。`web_fetch` 最多并行读取 4 个公开文本页面。网络访问只允许 HTTP(S)，拒绝内网、loopback、链路本地目标和非常用端口，并在重定向后重新解析和验证地址。网页正文和搜索摘要始终按不可信输入处理。

## 前端结构

桌面根入口是 `frontend/src/main.tsx`。不带查询参数时渲染应用级功能大厅 `ApplicationHome.tsx`；`?surface=workbench` 渲染完整 `App.tsx`，`/literature/index.html` 渲染文献特化前端，`/transcription/index.html` 渲染无 session 的会议转写工具，`/writing/index.html` 渲染无 session 的文章处理工具。大厅是四个功能的同级导航层，使用同尺寸 2×2 卡片，窄屏退化为单列。五个前端表面复用同一桌面后端、`sessionStorage` 动态 API 地址、`localStorage` 认证与外观状态；页面切换不复制项目、session、转写任务或文章历史。

完整工作台采用 IDE 式布局：

1. 48px 活动栏，只保留返回功能大厅与打开/关闭设置；文献特化前端复用相同结构、类名和皮肤槽位；
2. 项目、文件、会话或设置侧栏；
3. 中央对话与上下文区；
4. 可调整宽度的文件查看器；
5. 底部状态栏。

项目列表按注册目录的最近父子关系构树，同级按名称排序。文件树按目录优先、深度优先稳定展示，切换项目时目录默认折叠；工具改动触发刷新时只保留仍存在目录的展开状态。`fileEntryVisual()` 按目录和常见科研文件扩展名返回图标与类型标签。切换项目会重新加载项目会话、文件树和记忆；生成中禁止切换以避免活动任务跨项目。

完整工作台与文献智库都通过 `PATCH /api/work/sessions/{id}` 更新同一份 session meta 标题。工作台提供双击标题和常驻操作按钮的行内编辑，文献智库在当前 session 选择器旁提供居中重命名窗口；两处都限制非空且最长 80 个字符，只更新标题投影，不改写 JSONL 消息或上下文边界。

消息时间线把同一 `tool_call_id` 的开始和结果合并为一张状态卡。读者接近底部时自动跟随流式内容；向上滚动会暂停并显示「回到最新」。工具修改文件后，前端在本轮结束时刷新文件树和当前预览。

文献前端调用同一个 `/api/work/sessions/{id}/chat/stream` 并直接消费 `system_message`、`context_usage`、`text_delta`、`tool_call_start`、`tool_result`、`loop_continue`、`cancelled` 与 `done`。用户消息立即进入本地时间线；若本轮前有待显示的文献导入或选择 system 事件，reducer 会把正式事件插在乐观用户消息之前。正文增量逐段增长，工具开始立即建立一张运行中卡片，结果按 `tool_call_id` 更新同一卡片，后续正文另开段落，因此保持“系统背景 → 用户 → 文字 → 工具 → 文字”的真实顺序。`loop_continue` 只更新本轮临时进度提示；收到 `done`、终端错误或最终 session 回读成功后立即清空，停止事件则替换为明确的停止状态。工具结果只要带有真实 `changed_paths`（包括批次部分成功）就会经过 120ms 合并后分类刷新 catalog、tags、groups、notes 与文件投影；终端事件仍执行一次全量校准，避免旧工具结果漏刷新。消息容器只在用户仍接近底部时跟随增量；主动上滚会暂停并显示「回到最新」，与完整工作台一致。本轮结束后重新读取正式 session/JSONL，以持久化记录校准临时流式状态。对话头部的项目笔记控件为 SVG 与数量徽标保留独立的不可收缩 flex 槽位，避免按钮变窄时图标先被压缩。

会议转写前端不调用任何 `/sessions` 接口。左侧列表由 `/api/transcription/jobs` 每次从任务目录重建，当前选中任务 ID 只作为 `localStorage` UI 偏好；切到共享设置或以后用通用工作台打开同一目录再返回时，它只尝试恢复仍存在的 ID，否则选择最新任务。上传支持多文件并逐个流式写入本地输入目录，后端排队后前端轮询固定任务状态；完成后读取说话人分段、纯文本、Markdown 与已有 AI 派生结果。AI 按钮不会自动调用模型；每次生成或重新生成都先展示费用、隐私与原文不覆盖确认，进行中切换其它文件也不会把返回结果显示到错误任务。删除、恢复和 AI 结果清除都调用后端服务，前端不直接移动或覆盖本地文件。

文章处理前端同样不调用 `/sessions`。`WritingApp.tsx` 在左右等宽编辑区显示输入与输出，顶部只提供“文字润色”和“查找漏洞”两个模式，左侧历史区按需读取详情并提供可恢复删除。用户修改已打开历史的输入后会脱离当前记录，再处理时创建新记录而不是覆盖；“新任务”通过纯状态初始化器保留当前模式，清空输入、输出与历史选中，并在模型处理期间禁用。共享设置使用 `return=writing` 返回原页面。HUD 布局保留独立的文章标题栏作为第二网格行，功能大厅与模型设置入口不会随皮肤顶栏隐藏；工作区和状态栏依次位于第三、第四行。结果面板提示 Unicode 示例 `H₂O`、`10⁻³`、`R²`，但复杂公式仍保持原状。页面只有用户点击开始处理才请求模型。

AI 回复、压缩摘要和 Markdown 文件预览共用 `MarkdownRenderer.tsx`。渲染器启用 `remark-gfm`，把管道表格解析为语义化 HTML；table 外层滚动容器避免宽列撑破聊天布局。聊天气泡为 `ul/ol` 恢复显式左内边距，避免全局 reset 后的 outside marker 落入 Neon 切角或气泡边界。

文件面板支持 UTF-8 文本、Markdown 预览/编辑、PDF 和常见图片。二进制格式不会作为文本读取。`PdfViewer.tsx` 是完整工作台与文献智库共享的 PDF 阅读外壳；它通过 `/work/projects/{slug}/fs/media` 获取经过扩展名、大小、magic bytes 和项目相对路径校验的响应，转成短生命周期 `blob:` URL 后再交给 iframe 的浏览器原生 PDF 界面。组件切换文件或卸载时会中止请求并撤销 Blob URL。这样既不直接暴露任意本地路径、不维护第二套文献 PDF 阅读器，也避免下载接管扩展或外部下载软件截获 iframe 的原始 HTTP PDF 导航。

### 首次引导、教程任务与成就

`frontend/src/onboarding.ts` 是纯状态模型：定义首次引导阶段、六项教程任务、十个成就及产品事件到任务/成就的映射；解析本地状态时只保留白名单 ID，损坏或未来版本状态回退到欢迎页。`OnboardingUI.tsx` 只负责欢迎/模型/入口向导、DOM 高亮指引、教程任务卡、成就提示和设置页成就列表。

同一状态模块还维护 DeepSeek 官方入口、Base URL 和推荐模型预设；`applyDeepSeekPreset()` 保留现有 API Key，只替换 URL 和模型名。申请教程同时显示在首次向导和常规设置页，并明确指向开放平台的「创建 API Key」按钮及一次性复制步骤。MinerU 引导同样提供官方 API 管理页的 Token 创建、复制和设置粘贴路径。外部按钮通过 Tauri Opener 交给系统浏览器；桌面 capability 只放行 `platform.deepseek.com/*`、`api-docs.deepseek.com/*`、`mineru.net/*`、`bailian.console.aliyun.com/*`、`help.aliyun.com/*` 与 `mailto:*`，前端不能借此打开任意地址。会议转写引导捕获百炼外链打开失败并显示原始官方 URL，避免 capability 或系统浏览器异常被静默吞掉。

状态保存在当前桌面 WebView 的 `localStorage` 键 `workmode-public-onboarding-v1`，不进入后端数据目录、项目文件、JSONL 或模型上下文。正式构建中的所有解锁都来自真实前端事件：模型探测成功、项目创建、PDF 打开、消息发送、成功工具结果、Markdown 保存、上下文查看和手动压缩。Vite `DEV` 入口以及一键源码启动器显式注入的 `VITE_WORKMODE_SOURCE_ACHIEVEMENTS=1` 会在读取外观之前调用 `ensureDevelopmentAchievements()`，为源码调试环境补齐全部白名单成就并写回同一键；Release 和桌面生产构建不设置该变量，因此不改变安装包用户的解锁语义。React 状态更新器保持纯函数；独立 effect 负责一次性成就提示，避免 StrictMode 重复触发副作用。

文献智库不复用工作台的首次向导阶段。`frontend/src/literature/onboarding.ts` 用独立的 `workmode-public-literature-onboarding-v1` 状态维护四步引导：界面与数据边界、PDF 确认入库、默认按需阅读与可选 MinerU 增强、选择资料并自然语言协作。`LiteratureOnboarding.tsx` 只在文献页面渲染，完成或跳过后不再显示；普通阅读不把 Token 配置当作前置步骤，需要表格、公式、复杂版面或扫描件增强时才引导到官方说明或共享设置。设置页可以单独重置引导。文献页打开共享设置时，工作台 `FirstRunWizard` 与 `GuidedTour` 被抑制，避免旧引导串场。两套引导状态都只在本机 UI 层，不注入模型上下文。每个新文献 session 另由后端持久化一条 assistant 自我介绍，属于正式对话历史而非 UI 引导状态；既有历史 session 不被批量改写。

### 快速问题反馈

`frontend/src/bugReport.ts` 负责生成不接收项目状态、目录、会话、消息或模型密钥的说明模板；`BugReportDialog.tsx` 展示随安装包编译的公众号二维码、复制与邮件入口，并把桌面版的一键生成动作交给 `frontend/src/desktop.ts`。后者调用 `desktop_generate_bug_report`，成功后使用 Opener 的 `reveal_item_in_dir` 让系统文件管理器定位 ZIP；没有上传端点，也不会自动发送。

`desktop/src-tauri/src/diagnostics.rs` 是错误报告的权威实现。每次 Tauri 启动创建独立 `run-id` 和 `logs/runs/<run-id>/`，记录桌面生命周期、前端 `window.error`/`unhandledrejection` 事件与该次 Python 后端的 stdout/stderr；启动参数关闭 Uvicorn access log，避免带 `path` 或 `token` 的请求 URL 落盘。运行目录只保留最近 20 个，项目、会话、JSONL 和工作记忆不属于该清理范围。

生成报告时只读取当前 run，每个日志文件只取末尾最多 512 KiB，并在导出前再次替换认证字段、常见密钥和 Windows/UNC 本地路径。ZIP 固定包含 `report.md`、`manifest.json`、`current-run.log`，保存到 `%LOCALAPPDATA%\WorkmodePublic\reports\`；报告文件是用户管理的本地产物，应用不自动删除。桌面 capability 仅增加 `opener:allow-reveal-item-in-dir`，不授予任意路径打开或网络上传能力。

引导高亮通过固定 `data-guide` 锚点定位项目、文件、聊天、上下文、文件查看器和输入框。用户可以跳过并在设置中重新播放。教程重置只重置任务清单；历史成就保留。

### 皮肤与可访问性

`frontend/src/theme.ts` 定义稳定主题 ID、主题元数据、本地偏好解析、系统明暗映射和成就解锁规则。`main.tsx` 在首次 React render 前应用主题，避免启动时先闪现默认深色；`App.tsx` 监听 `prefers-color-scheme` 并把选择写入 `workmode-public-theme-v1`。该状态不进入后端、项目、会话或模型上下文。

内置主题与官方签名皮肤复用同一套业务组件和状态。`theme.ts` 负责稳定基础主题、系统明暗映射和内置成就解锁；外部皮肤不能复制项目、文件、会话、消息、工具、上下文、设置或查看器状态。React 只通过稳定的 `data-skin-slot` 与 `data-skin-icon` 暴露真实内容接点，新增可展示数据必须先进入核心组件契约。结构主题的顶栏统一由 `SkinChrome.tsx` 渲染：根入口把已解析的主题与活动签名皮肤传给功能大厅，文献入口传给 `LiteratureApp`，会议转写入口传给 `TranscriptionApp`，文章处理入口传给 `WritingApp`，完整工作台继续使用自身的动态外观状态；各处只向顶栏提供当前页面已有的真实状态，不维护第二份遥测数据。

0.7.0 的皮肤引擎以签名包为执行边界。`skinPackage.ts` 在解析 manifest 或 CSS 之前检查 ZIP 路径、条目和体积，核对 `signature.json` 的完整文件集合、大小与 SHA-256，并用 `officialSkinKeys.ts` 中的 Ed25519 公钥验签。只有完整通过的 `.workmode-skin` 才会进入 `skinLibrary.ts` 的 version 4 本地库和 `skinAssetStore.ts` 的 `workmode-public-official-skins-v1` IndexedDB。旧 JSON 导入、本地库 version 1/2/3 和 `workmode-public-skins-v3` 资源库都不会迁移；`main.tsx` 会清理这些旧入口。

皮肤维护与应用发行是两条独立流水线。公开仓库只保存协议、导入器、运行时和离线签名工具；奖励皮肤源码、静态样稿、字体、本地验签清单和签名包统一位于维护机被 Git 忽略的 `local-reference/reward-skin-library/`。`scripts/build-skin-library.ps1` 默认读取该本地库，也接受显式 `-SourceRoot` 与 `-PackageRoot`；它只把协议文件、manifest 声明素材和许可证复制到临时净化目录，再调用离线 Ed25519 签名器。公开测试对私有库只运行可选视觉回归，应用核心构建和测试不依赖其存在。桌面构建脚本与 GitHub Actions 不读取 `local-reference/`；公开 Release 只包含应用安装、更新和校验产物。

签名包中的 `layout.css` 负责语义槽位的排列、尺寸和响应式降级，`visual.css` 负责配色、字体、材质、边框、图标、背景和动画。功能大厅公开 `feature-*` 槽位，文献页面公开 `literature-*` 与共享聊天槽位，会议转写公开 `transcription-*` 槽位，文章处理公开 `writing-*` 槽位；它们先复用基础主题变量和当前签名皮肤资源，再允许未来皮肤按专用槽位做布局适配。颜色链固定为“基础主题或签名皮肤 palette → `themeContract.css` 的 `--ui-*` 应用语义 → 页面局部别名”。带结构顶栏的页面根节点统一增加 `hud-layout`，但工作台、功能大厅、文献智库、会议转写和文章处理各自维护与自身内容匹配的网格规则；内置 Neon 在五个表面使用同一个舰桥顶栏，并分别投影真实功能卡、IDE 面板、文献/对话面板、转写队列和文字处理区。`skinAssetRuntime.ts` 把 `workmode-asset://<asset-id>` 替换成临时 Blob URL，加载当前皮肤的 FontFace，并把两段已验签 CSS 注入带皮肤 ID 的 `<style>`；切换、停用或移除时撤销样式、URL 和字体。CSS 没有 JavaScript、HTML 或 Tauri 权限入口，但它是受信任的界面代码，因此只能由项目官方审核并用离线私钥签名。

恢复策略独立于皮肤 CSS：开始加载时写入 boot guard，稳定三秒后清除；若加载阶段崩溃，下次启动自动停用该皮肤。资源或 CSS 加载失败也会立即回退基础主题。`Ctrl+Alt+Shift+R` 会清除官方皮肤选择和旧皮肤存储并刷新，不触碰项目、会话、JSONL、工作记忆或模型配置。详细包格式、语义槽位和密钥纪律见 `docs/CUSTOM-SKINS.md`。

实验室、论文纸、深夜观测站、高对比及跟随系统始终可选；Origin Ring 与 Neon Space Lab 依赖本地 `tutorial_graduate` 成就。降低动效既支持用户显式开关，也尊重操作系统 `prefers-reduced-motion`。高对比主题额外强化键盘焦点和选中边界。

设置内容不再受 280px 项目侧栏宽度限制。`App.tsx` 在设置活动时给根网格增加 `settings-open`，保留活动栏和可选 HUD，隐藏聊天与文件工作区，让原 `side-panel` 跨越余下全部列；`settings-panel` 使用固定区域的响应式两列卡片网格：模型与 MinerU 并排，DashScope、主题和项目记忆跨满两列，应用支持、引导成就和连接组成下半区，窄屏按同一信息层级退化为单列。所有卡片统一宽度规则、内边距、圆角和拉伸方式；问题反馈收进“桌面应用与支持”卡片的次级区域。`PUT /api/settings/mineru` 与 `PUT /api/settings/dashscope` 分别保存对应密钥，设置响应只返回是否已配置，不回显 Token。文献页、转写页和文章处理页分别使用 `return=literature|transcription|writing` 打开同一设置页；再次点击设置按钮时返回原入口，不复制设置状态或触发工作台首次向导。

## 桌面生命周期与更新

`desktop/src-tauri/src/lib.rs` 负责单实例、托盘、窗口、动态端口后端和退出清理。后端使用 `PYTHONDONTWRITEBYTECODE=1`，避免在安装目录生成运行缓存。

更新器下载带 minisign/Tauri 签名的安装器。安装前，前端调用 Rust 生命周期命令停止并等待 Python 后端进程树，避免已加载 `.pyd` 锁住 NSIS 需要替换的文件；若安装启动在应用退出前失败，可以在原端口恢复后端。

更新公钥编译进应用，私钥和密码只存在本地忽略目录或 GitHub Actions secrets。该签名不等于 Windows Authenticode。

旧版便携数据导入由 `desktop/src-tauri/src/migration.rs` 实现。它只接受包含有效 `data/work` 的旧目录，目标桌面数据非空时拒绝合并，通过 staging 目录复制 `data/` 和可选 `config/.env`，且不修改来源。

## 仓库职责

```text
backend/                         后端实现和回归测试
frontend/                        React 多页面实现和 Vitest；功能大厅/主工作台 + 文献智库 + 会议转写 + 文章处理
desktop/src-tauri/               Rust/Tauri 实现、能力声明和 Windows 图标
desktop/src-tauri/resources/     构建时生成的后端/runtime staging；不提交内容
tutorial-project/                官方教程的版本化初始模板和项目级提示词
literature-demo/                 文献固定项目模板、领域说明和退役原型归档
scripts/build-desktop.ps1        本地桌面构建、测试、签名和产物生成
scripts/sync-version.ps1         同步全部版本源
.github/workflows/               正式 Windows Release 流程
docs/                            当前架构、开发、发行和路线图
```

### 文献特化 Workmode 项目

论文回收投影由 `DELETE .../literature/papers/{paper_id}`、`GET .../literature/trash/papers` 与 `POST .../literature/trash/papers/{trash_id}/restore` 提供；三者和 AI 的删除/恢复工具进入同一领域 executor，不另建状态源。

`literature-project.json` 是项目模式开关。注册项目时不复制 session 或数据库；后端每次按项目根目录读取 manifest，识别 `project_type=literature-library`、`schema_version=2`、`tool_profile=literature`。schema v1 项目进入时原地迁移，不搬动现有 PDF。项目模板使用英文固定结构：根目录保存 manifest、`WORKMODE.md`、`LITERATURE_PROJECT.md`、`catalog.json`、`tags.json`、`groups.json`、`processed-index.md`；受控内容位于 `papers/unprocessed|processed/pdf|SI|extracted/`、可恢复文献回收站 `papers/.trash/`、`notes/` 和 `exports/`。

文献模式仍调用正式 `/api/work/sessions/{id}/chat/stream`。`storage.py` 保存同一套 session meta 和 JSONL，`TurnRecorder` 保存同一套 `tool_call_start`/`tool_result`，`build_context_window()` 与 `session_compactor.py` 处理同一套 token 预算、摘要边界和历史。文献前端默认读取最新 60 条消息并按 `tool_call_id` 合并工具卡；旧独立 chat/store/compactor/routes 已退役到 `literature-demo/archive/standalone-backend-2026-07-13/`，FastAPI 不导入该目录。

`project_tool_schemas(project_slug)` 根据项目类型返回工具画像。普通项目仍得到通用项目、Web、memory 和 plan 工具；文献项目只得到 16 个 `literature_*` 工具，明确不加载 Shell、Python、通用文件、Web、通用 memory 和 plan。`literature_library_overview` 从 `catalog.json`、`groups.json`、`tags.json` 和 `LITERATURE_FIELD_REGISTRY` 返回论文总数、处理状态、元数据完整度、资产登记数、真实文献分组及使用数、彩色标签组及使用数和共享字段契约；它明确把文献分组与标签组分开，禁止模型根据 `papers/` 的物理目录猜逻辑分类。只读 `literature_read` 同时接受一个 `paper_id` 或最多 20 个 `paper_ids`，批量读取以最多 3 个线程隔离单篇失败；它不创建解析任务。`literature_search` 支持按文献分组 ID 和标签 ID 过滤，并与 `literature_read(part="record")` 共用同一记录投影：除稳定 ID 外返回书目字段、元数据质量、处理/校验状态、PDF/SI/解析路径，以及解析后的人类可读文献分组和标签名称。`literature_tag_list` 只负责权威 `tags.json` 标签注册表，返回真实标签组及其颜色，以及规范标签 ID、名称、别名、组 ID、状态和按 `catalog.json.tag_ids` 计算的使用次数；它不再被描述成文献分组工具，前端也不维护硬编码标签分类。`literature_update_record` 的 schema 描述要求写标签前先调用它并复用已有规范标签，也允许更新 `publication_date`。`literature_delete` 与 `literature_restore` 提供论文级可恢复删除；`literature_note_delete` 把普通 `notes/*.md` 移入 `notes/.trash/` 并拒绝删除固定 README。删除结果通过 `changed_paths` 触发投影刷新。模型产生的文献写工具会在结构校验后直接执行，不存在 proposal、confirm/reject 工具、`confirmed` 字段或确认关键词解析。前端选择的论文和笔记随用户消息写入 `meta.active_context`；论文选择变化还会先写入 `literature_selection_changed` system 事件，Prompt 用其 paper ID 元数据生成紧凑机器引用，历史 UI 显示的正文只保留文件名。选择只提高本轮相关性，任何真实 paper ID 都可被领域工具处理，选择状态不是授权。用户明确要求精读单篇论文时，文献系统 Prompt 将默认回答切换为逐图证据讲解：先读真实正文与图注，再按图和 panel 说明实验、观察、论证作用与局限；证据不足必须明示且不得猜图，MinerU 增强解析需要先取得用户同意。

`literature_project.py` 是固定结构与原子写入边界。`catalog.json`、`groups.json` 和 `tags.json` 是机器权威源；`LITERATURE_FIELD_REGISTRY` 给人类投影和 AI 工具提供同一字段契约，并为每个字段声明可编辑、可搜索、可筛选、前端可见和 AI 可见状态及人类语义。当前对齐的用户字段包括标题、作者、第一作者姓、年份、发表日期、期刊、期刊缩写、DOI、Workmode 文章类型、文献分组、标签、关注点、摘要、元数据来源/完整度/问题、处理/校验状态、标准档名、归档位置和 PDF/SI/MinerU/全文/事实报告路径；内容哈希与内部时间戳保留为内部字段。前端详情与 AI 记录投影消费同一语义，前端搜索也覆盖 DOI、第一作者姓和期刊缩写。领域工具负责标签注册、记录、笔记、跨文献段、归档和回收同步。论文删除先锁住 catalog、预检所有受控来源与回收目标，再把主 PDF、SI 文件夹和最外层解析目录移动到 `papers/.trash/<时间>--<paper-id>/files/<原相对路径>`，同时保存含完整记录、原列表位置和移动路径的 `manifest.json`；任一步失败即回滚文件与 catalog。恢复同样先检查所有原目标不存在，再按 manifest 原路移动并重建 `processed-index.md`，绝不覆盖。session/JSONL 属于不可变历史，不参与论文删除。`literature_update_record` 先在内存中规范化并校验候选元数据，再提交 catalog/tag 变更；期刊缩写允许带点、空格和常见标点，标准命名时自动收敛为纯字母数字 CamelCase 片段。标准命名校验失败时不写入候选记录或候选标签，避免失败工具调用造成半写入。通用 Markdown 编辑接口在文献项目中只允许修改既有 `notes/*.md`，协议、catalog、分组、标签、索引和论文产物必须经领域服务。PDF 上传流式写入 `papers/unprocessed/pdf/`，校验 `%PDF-` 并按 SHA-256 去重；重复内容不创建第二条记录，文件名碰撞不会覆盖。

`endnote_import.py` 以 SQLite 只读 URI 打开 `.enl`，附件只从同名 `.Data/PDF` 读取；`.enlx` 只把 `sdb/sdb.eni` 解到临时目录，其余附件从 ZIP 流式读取，并修复常见的 UTF-8 文件名被标成 CP437 的情况。自动发现通过 Windows 卷 API 枚举全部固定盘和可移动盘（其它平台使用文件系统根），最多并行扫描四个卷；遇到无权限路径或链接直接跳过，不进入任何 `*.Data` 附件树。同一父目录、同名 stem 的 `.enl`/`.enlx` 聚合成一个候选，优先选择带同名 `.Data` 的工作库，其次选择压缩库，最后才显示缺少 `.Data` 的孤立 `.enl`。扫描不包含任何网盘品牌或特定用户路径硬编码。导入字段固定为标题、作者、年份、发表日期、期刊和 DOI，不复制 EndNote reference type 或其它暂时无用途的字段。只接受 `TYPE;3` 手工分组，舍弃智能分组；读取 `misc.code=17` 的分组集成员关系后，以“分组集 - 手工分组”拍平层级；`TYPE;10` 标签按真实颜色创建项目标签组。每条记录遍历全部附件，首个扩展名为 PDF 且 magic bytes 为 `%PDF-` 的文件成为主论文，其余现存附件进入 `papers/unprocessed/SI/<paper-id>/`。无有效 PDF 的记录记录为单项失败，不取消其它记录。导入时只有标题、作者、年份和期刊都存在才标记 `metadata_trust=complete`；既有 catalog 中不可能成立的 `complete` 状态会在读取投影时降级为 `partial` 并返回缺失字段说明，但只读操作不暗改磁盘文件。导入不按来源预合并；用户可在完成后调用重复扫描，以 DOI、主 PDF SHA-256、规范化标题+年份+第一作者生成候选对，扫描本身不修改 catalog。

`literature_pipeline.py` 是用户明确要求增强解析、结构化事实或归档时才进入的高级路径；PDF 入库、勾选和普通问答都不会自动调用它。它在一次正式工具调用内完成 MinerU、元数据和客观事实抽取，不建立独立任务/session 表。`literature_process` 同时接受一个 `paper_id` 或一组 `paper_ids`；批量调用使用最多 3 个工作线程，每篇独立收口成功/失败结果，并用按项目根目录分配的重入锁保护 catalog 的读改写与标准命名碰撞检查。MinerU 结果进入 `papers/unprocessed/extracted/<paper-id>/`；已有非空 `full.md` 会直接复用，后续阅读也优先使用它，事实报告为 `objective-facts.md`。同一个 `literature_read(part="full_text")` 在 `full.md` 缺失时调用 `pdf_text.py` 从原 PDF 本地文本层读取，并在工具结果中返回 `source=pdf_text_layer`、页数、截断信息和局限警告；有 MinerU 结果时返回 `source=mineru_markdown`。本地兜底不做 OCR，扫描件/纯图片 PDF 会明确要求 MinerU/OCR；复杂表格、公式和多栏版式仍推荐 MinerU。元数据只读首页 `Cite This`，ACS/Elsevier 页眉缺失时读取既有 `layout.json` DOI 邻近块；模型请求使用 Chat Completions `response_format={"type":"json_object"}`，原始响应写入解析目录，JSON 失败只进行一次同约束修复。声明的证据必须是首页或回退文本的规范化逐字子串；无法解析、缺字段或证据不成立时记录 `metadata_issue`、保持 `metadata_trust=partial`，但不阻断客观事实报告。前端在详情页明确显示人工确认提示，用户补齐作者姓、年份和期刊缩写后由 `literature_update_record` 完成标准命名。标准名为 `Surname_Year_Journal.pdf`，碰撞追加 `_2`、`_3`。默认 MinerU 等待 180 秒，设置页或 `WORKMODE_MINERU_TIMEOUT_SECONDS` 可在 60–1800 秒范围调整；流水线与设置 API 读取同一份热更新 `Settings`。停止生成把 cancellation event 传入 MinerU 与本地 PDF 阅读；网络步骤结束、轮询间隙或逐页抽取时会终止，工具结果按正式 JSONL 取消语义收口。

`literature_routes.py` 只提供固定文件到前端模型的投影：创建/识别文献项目、列出 catalog/groups/tags/fields/notes、EndNote 自动发现/预检/导入、重复扫描、上传 PDF、读取事实/PDF、返回 SI 本地路径、直接更新或删除笔记、更新记录/跨文献段和执行归档。它不是第二个对话后端。`POST /api/work/literature-projects` 的新客户端只传名称；后端通过 `WORKMODE_MANAGED_PROJECTS_DIR` 分配托管目录，默认优先 `D:\workmode`、无 D 盘时使用 `~/workmode`，目录冲突追加数字。旧客户端仍可传 `root_path`，旧注册项目在原路径零复制兼容；进入投影时幂等补齐缺失固定目录和文件，不覆盖权威数据。项目响应派生 `storage_mode=managed|external`，不要求迁移 storage JSON schema。活动前端位于 `frontend/src/literature/`，由 `frontend/vite.config.ts` 与功能大厅、主工作台、`frontend/src/transcription/` 和 `frontend/src/writing/` 一起构建为 `dist/index.html`、`dist/literature/index.html`、`dist/transcription/index.html` 与 `dist/writing/index.html`；Tauri 继续只打包一份 `frontend/dist`。应用级功能大厅只负责进入文献页面；项目新建、切换、重命名和安全移除位于文献页居中项目管理窗口。移除继续复用共享项目软删除，不删除实体目录。完整工作台不再承担跨模块导航。文献页复用工作台的 `activity-bar` / `activity-btn` 和 `activity-navigation` 皮肤槽位，在左侧提供功能大厅与全局设置；顶部仅保留模块品牌和当前项目，不显示重复的后端连接或特化模式徽章。文献详情、项目笔记和项目记忆都由统一的全屏 backdrop 居中承载；原始 PDF 页签直接使用共享 `PdfViewer`，根据 catalog 中受控的 `paths.pdf` 调用通用 `api.mediaUrl()`。页面切换通过同源 URL 完成，动态桌面 API 地址和目标项目 slug 暂存在同一 WebView 的 `sessionStorage`，认证 token 继续读取共享 `localStorage`。拖拽 PDF 只建立前端待确认清单；确认后才上传，上传完成不会自动勾选文献或启动模型。EndNote 导入由桌面文件选择器提供 `.enl`/`.enlx` 路径，后端预检成功且用户确认关闭 EndNote 后才复制；它不产生聊天请求。SI 路径由受控项目记录解析，Tauri 只在用户点击“打开 SI 文件夹”时调用本地 opener。Windows 桌面窗口在 `tauri.conf.json` 中固定 `dragDropEnabled=false`，避免 Tauri 原生拖放拦截 WebView 的 HTML5 `FileList`；浏览器源码模式和安装版因此共用同一条前端确认入库链。批次完成后，后端在同一正式 session 中追加 `literature_import_confirmed` system 事件，正文只有“用户刚刚导入了以下文献”及文件名，paper ID 只保存在元数据；Prompt 构建时从当前 catalog 补充紧凑机器引用，不信任前端编写 paper ID。前端在该事件后出现下一条用户消息之前暂不显示它；下一轮开始时后端通过 `system_message` SSE 把事件放到乐观用户消息之前，最终 JSONL 回读后永久保留。项目标题和 token 百分比来自正式项目记录及 `/context` 结果，不使用静态占位或第二套后台任务轮询。归档在移动任何文件前预检 PDF、SI 与解析目录的所有目标位置，避免目标碰撞导致半归档。

通用的特化模块开发流程、manifest 字段和分层边界见 [SPECIALIZED-MODULES.md](SPECIALIZED-MODULES.md)。

文献页顶部的 session 选择器与重命名入口复用上述共享会话元数据；文献目录、catalog 和独立前端状态都不保存第二份标题。

早期 0.1.x 便携包的构建器、CMD 更新器和 manifest 示例已经从当前仓库移除；其数据格式仍由桌面迁移器兼容。Android、iOS、macOS 和 Microsoft Store 图标不属于当前 Windows NSIS 目标，不提交到仓库。

## 当前安全边界与待加强项

已有边界：loopback 默认绑定、可选本地 token、窄 CORS、项目路径沙箱、媒体白名单、命令限制、网页 SSRF 防护、签名更新、用户数据与安装目录分离。

仍待加强：

- Windows Authenticode；
- 更清晰的本地 token 首次配置体验；
- 首次安装、升级、卸载保留数据的端到端 smoke test；
- 完整的文献元数据、DOI 去重和可核验引用流水线；
- 子 agent 的权限、预算、取消与文件冲突设计。
