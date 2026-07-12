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
    backups\history-repair\
  logs\
```

直接运行后端时，若未设置覆盖变量，Windows 默认数据目录是 `%APPDATA%\WorkmodePublic`，其他系统是 `~/.workmode-public`。

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

`web_search` 最多并行处理 5 个 query，每个最多返回 8 条。默认检索源是 `cn.bing.com/search?format=rss`：免 API Key、国内可直连，跟随到 Bing 中国实际 RSS 地址后以标准 XML 解析标题、直链和纯文本摘要，结果载荷明确标记 `engine=bing-cn-rss`；不再依赖 DuckDuckGo。`web_fetch` 最多并行读取 4 个公开文本页面。网络访问只允许 HTTP(S)，拒绝内网、loopback、链路本地目标和非常用端口，并在重定向后重新解析和验证地址。网页正文和搜索摘要始终按不可信输入处理。

## 前端结构

入口是 `frontend/src/App.tsx`。界面采用 IDE 式布局：

1. 48px 活动栏；
2. 项目、文件、会话或设置侧栏；
3. 中央对话与上下文区；
4. 可调整宽度的文件查看器；
5. 底部状态栏。

项目列表按注册目录的最近父子关系构树，同级按名称排序。文件树按目录优先、深度优先稳定展示，切换项目时目录默认折叠；工具改动触发刷新时只保留仍存在目录的展开状态。`fileEntryVisual()` 按目录和常见科研文件扩展名返回图标与类型标签。切换项目会重新加载项目会话、文件树和记忆；生成中禁止切换以避免活动任务跨项目。

消息时间线把同一 `tool_call_id` 的开始和结果合并为一张状态卡。读者接近底部时自动跟随流式内容；向上滚动会暂停并显示「回到最新」。工具修改文件后，前端在本轮结束时刷新文件树和当前预览。

AI 回复、压缩摘要和 Markdown 文件预览共用 `MarkdownRenderer.tsx`。渲染器启用 `remark-gfm`，把管道表格解析为语义化 HTML；table 外层滚动容器避免宽列撑破聊天布局。聊天气泡为 `ul/ol` 恢复显式左内边距，避免全局 reset 后的 outside marker 落入 Neon 切角或气泡边界。

文件面板支持 UTF-8 文本、Markdown 预览/编辑、PDF 和常见图片。二进制格式不会作为文本读取。PDF/图片通过经过校验的媒体端点提供，而不是直接暴露任意本地路径。

### 首次引导、教程任务与成就

`frontend/src/onboarding.ts` 是纯状态模型：定义首次引导阶段、六项教程任务、十个成就及产品事件到任务/成就的映射；解析本地状态时只保留白名单 ID，损坏或未来版本状态回退到欢迎页。`OnboardingUI.tsx` 只负责欢迎/模型/入口向导、DOM 高亮指引、教程任务卡、成就提示和设置页成就列表。

同一状态模块还维护 DeepSeek 官方入口、Base URL 和推荐模型预设；`applyDeepSeekPreset()` 保留现有 API Key，只替换 URL 和模型名。申请教程同时显示在首次向导和常规设置页。外部按钮通过 Tauri Opener 交给系统浏览器；桌面 capability 只放行 `platform.deepseek.com/*` 与 `api-docs.deepseek.com/*`，前端不能借此打开任意地址。

状态保存在当前桌面 WebView 的 `localStorage` 键 `workmode-public-onboarding-v1`，不进入后端数据目录、项目文件、JSONL 或模型上下文。所有解锁都来自真实前端事件：模型探测成功、项目创建、PDF 打开、消息发送、成功工具结果、Markdown 保存、上下文查看和手动压缩。React 状态更新器保持纯函数；独立 effect 负责一次性成就提示，避免 StrictMode 重复触发副作用。

### 快速问题反馈

`frontend/src/bugReport.ts` 负责生成脱敏诊断模板和 `mailto:` 链接，`BugReportDialog.tsx` 负责展示随安装包编译的公众号二维码、复制按钮和邮件入口。模板只接收应用版本、desktop/web 运行形态、浏览器平台字符串、界面语言、主题和当前本地皮肤 ID，不接收项目状态、目录、会话、消息或模型密钥。

二维码是本地静态资源；打开弹窗不会产生网络请求，也不会自动发送任何信息。桌面 capability 只额外放行 `mailto:*`，由系统默认邮件客户端承接草稿，最终发送仍由用户确认。公众号反馈同样需要用户主动复制诊断模板并私信。

引导高亮通过固定 `data-guide` 锚点定位项目、文件、聊天、上下文、文件查看器和输入框。用户可以跳过并在设置中重新播放。教程重置只重置任务清单；历史成就保留。

### 皮肤与可访问性

`frontend/src/theme.ts` 定义稳定主题 ID、主题元数据、本地偏好解析、系统明暗映射和成就解锁规则。`main.tsx` 在首次 React render 前应用主题，避免启动时先闪现默认深色；`App.tsx` 监听 `prefers-color-scheme` 并把选择写入 `workmode-public-theme-v1`。该状态不进入后端、项目、会话或模型上下文。

内置主题与官方签名皮肤复用同一套业务组件和状态。`theme.ts` 负责稳定基础主题、系统明暗映射和内置成就解锁；外部皮肤不能复制项目、文件、会话、消息、工具、上下文、设置或查看器状态。React 只通过稳定的 `data-skin-slot` 与 `data-skin-icon` 暴露真实内容接点，新增可展示数据必须先进入核心组件契约。

0.7.0 的皮肤引擎以签名包为执行边界。`skinPackage.ts` 在解析 manifest 或 CSS 之前检查 ZIP 路径、条目和体积，核对 `signature.json` 的完整文件集合、大小与 SHA-256，并用 `officialSkinKeys.ts` 中的 Ed25519 公钥验签。只有完整通过的 `.workmode-skin` 才会进入 `skinLibrary.ts` 的 version 4 本地库和 `skinAssetStore.ts` 的 `workmode-public-official-skins-v1` IndexedDB。旧 JSON 导入、本地库 version 1/2/3 和 `workmode-public-skins-v3` 资源库都不会迁移；`main.tsx` 会清理这些旧入口。

皮肤维护与应用发行是两条独立流水线。公开仓库只保存协议、导入器、运行时和离线签名工具；奖励皮肤源码、静态样稿、字体、本地验签清单和签名包统一位于维护机被 Git 忽略的 `local-reference/reward-skin-library/`。`scripts/build-skin-library.ps1` 默认读取该本地库，也接受显式 `-SourceRoot` 与 `-PackageRoot`；它只把协议文件、manifest 声明素材和许可证复制到临时净化目录，再调用离线 Ed25519 签名器。公开测试对私有库只运行可选视觉回归，应用核心构建和测试不依赖其存在。桌面构建脚本与 GitHub Actions 不读取 `local-reference/`；公开 Release 只包含应用安装、更新和校验产物。

签名包中的 `layout.css` 负责语义槽位的排列、尺寸和响应式降级，`visual.css` 负责配色、字体、材质、边框、图标、背景和动画。`skinAssetRuntime.ts` 把 `workmode-asset://<asset-id>` 替换成临时 Blob URL，加载当前皮肤的 FontFace，并把两段已验签 CSS 注入带皮肤 ID 的 `<style>`；切换、停用或移除时撤销样式、URL 和字体。CSS 没有 JavaScript、HTML 或 Tauri 权限入口，但它是受信任的界面代码，因此只能由项目官方审核并用离线私钥签名。

恢复策略独立于皮肤 CSS：开始加载时写入 boot guard，稳定三秒后清除；若加载阶段崩溃，下次启动自动停用该皮肤。资源或 CSS 加载失败也会立即回退基础主题。`Ctrl+Alt+Shift+R` 会清除官方皮肤选择和旧皮肤存储并刷新，不触碰项目、会话、JSONL、工作记忆或模型配置。详细包格式、语义槽位和密钥纪律见 `docs/CUSTOM-SKINS.md`。

实验室、论文纸、深夜观测站、高对比及跟随系统始终可选；Origin Ring 与 Neon Space Lab 依赖本地 `tutorial_graduate` 成就。降低动效既支持用户显式开关，也尊重操作系统 `prefers-reduced-motion`。高对比主题额外强化键盘焦点和选中边界。

设置内容不再受 280px 项目侧栏宽度限制。`App.tsx` 在设置活动时给根网格增加 `settings-open`，保留活动栏和可选 HUD，隐藏聊天与文件工作区，让原 `side-panel` 跨越余下全部列；`settings-panel` 再用宽屏双栏卡片组织桌面、模型、皮肤、成就、连接和项目记忆。返回项目活动页后恢复原网格，状态组件不卸载、不迁移数据。

## 桌面生命周期与更新

`desktop/src-tauri/src/lib.rs` 负责单实例、托盘、窗口、动态端口后端和退出清理。后端使用 `PYTHONDONTWRITEBYTECODE=1`，避免在安装目录生成运行缓存。

更新器下载带 minisign/Tauri 签名的安装器。安装前，前端调用 Rust 生命周期命令停止并等待 Python 后端进程树，避免已加载 `.pyd` 锁住 NSIS 需要替换的文件；若安装启动在应用退出前失败，可以在原端口恢复后端。

更新公钥编译进应用，私钥和密码只存在本地忽略目录或 GitHub Actions secrets。该签名不等于 Windows Authenticode。

旧版便携数据导入由 `desktop/src-tauri/src/migration.rs` 实现。它只接受包含有效 `data/work` 的旧目录，目标桌面数据非空时拒绝合并，通过 staging 目录复制 `data/` 和可选 `config/.env`，且不修改来源。

## 仓库职责

```text
backend/                         后端实现和回归测试
frontend/                        React 实现和 Vitest
desktop/src-tauri/               Rust/Tauri 实现、能力声明和 Windows 图标
desktop/src-tauri/resources/     构建时生成的后端/runtime staging；不提交内容
tutorial-project/                官方教程的版本化初始模板和项目级提示词
scripts/build-desktop.ps1        本地桌面构建、测试、签名和产物生成
scripts/sync-version.ps1         同步全部版本源
.github/workflows/               正式 Windows Release 流程
docs/                            当前架构、开发、发行和路线图
```

早期 0.1.x 便携包的构建器、CMD 更新器和 manifest 示例已经从当前仓库移除；其数据格式仍由桌面迁移器兼容。Android、iOS、macOS 和 Microsoft Store 图标不属于当前 Windows NSIS 目标，不提交到仓库。

## 当前安全边界与待加强项

已有边界：loopback 默认绑定、可选本地 token、窄 CORS、项目路径沙箱、媒体白名单、命令限制、网页 SSRF 防护、签名更新、用户数据与安装目录分离。

仍待加强：

- Windows Authenticode；
- 更清晰的本地 token 首次配置体验；
- 首次安装、升级、卸载保留数据的端到端 smoke test；
- 完整的文献元数据、DOI 去重和可核验引用流水线；
- 子 agent 的权限、预算、取消与文件冲突设计。
