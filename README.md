# Workmode Public

Workmode Public 是一个可独立安装、本地优先的纯净科研工作助手。它围绕项目文件、科研写作、实验记录、数据处理和可追踪的长期工作上下文设计，不包含私人伴侣、生活记忆或人格关系模块。

[下载最新 Windows 版本](https://github.com/carbocation123/workmode-public/releases/latest) · [查看发行记录](https://github.com/carbocation123/workmode-public/releases) · [报告安全问题](SECURITY.md)

## 主要能力

- 注册并切换多个本地项目，按真实父子目录关系展示项目；
- 为每个项目保存独立会话、项目工作记忆和任务计划；
- 浏览默认折叠的项目文件树，以图标区分目录、Markdown、PDF、图片、代码、实验数据和压缩包；预览 UTF-8 文本、Markdown、PDF 和常见图片；
- 在 AI 回复和文件预览中渲染 GitHub Flavored Markdown 表格，宽表可横向滚动；编辑已有 Markdown 时使用内容版本校验避免覆盖外部修改；
- 让模型读取、搜索、创建和精确编辑项目文件，也可以在项目目录运行受限的 shell 与 Python；
- 使用 `web_search` 并行检索公开网页，再用 `web_fetch` 核对原始页面；
- 在工作记忆中用 `@相对路径.md` 固定注入项目协议或其他 UTF-8 文本；
- 按 token 预算动态选择最近历史，并在界面显示估算总量、历史数量、固定导入文件数和摘要状态；
- 手动压缩上下文，保留完整 JSONL 历史，只改变后续模型的续接起点；
- 停止正在运行的生成和工具链，并按原始“文字 → 工具 → 文字”顺序持久化已产生内容；
- 从 GitHub Releases 检查、下载并安装经过 Tauri 更新签名验证的新版本；
- 首次启动时逐步配置并测试模型；内置 DeepSeek 开放平台注册、充值、创建 API Key 教程和 V4 Pro/Flash 一键预设；随后选择教程或自己的项目，再通过六步高亮指引认识界面；设置中可以随时重新播放；
- 从应用内创建官方科研协作教程，使用六项真实任务卡体验完整流程，并在测试后安全重置到内置初始态；
- 用本地成就记录模型连通、项目创建、PDF 阅读、网页检索、脚本分析、Markdown 保存、上下文查看与压缩等真实操作。
- 提供实验室、Origin Ring、论文纸、深夜观测站和高对比皮肤，可跟随系统主题并独立降低动效。

模型工具循环没有固定轮数上限。它会持续到模型给出最终正文、用户点击停止，或发生无法继续的模型/网络错误；普通工具失败会作为结果返回模型，由模型决定修正参数、换方法或向用户说明。

## 安装与首次使用

当前正式分发目标是 Windows x64。普通用户只需要从 [Releases](https://github.com/carbocation123/workmode-public/releases/latest) 下载：

```text
workmode-public-<version>-windows-x86_64-setup.exe
```

目标电脑不需要安装 Node.js、Python 或 Rust。安装完成后：

1. 从开始菜单启动 Workmode Public，首次启动向导会说明本地数据和模型请求边界；
2. 没有模型 API 时，展开「如何申请 DeepSeek API」，依次登录开放平台、充值 API 余额并创建 API Key；也可以继续填写其它 OpenAI-compatible Base URL、模型名和 API Key；
3. 选择「体验科研教程（推荐）」或「打开自己的项目」；
4. 跟随六步界面高亮认识项目、文件、时间线、上下文、文件查看器和输入框；
5. 教程项目右下角会显示六项真实任务，示例指令只填入输入框，由用户检查后按 `Ctrl+Enter` 发送；
6. 后续可以在「设置 → 外观与皮肤」即时切换主题，在「新手引导与成就」重新播放引导、查看成就或重置教程清单，在「桌面应用」检查更新。

向导每一步都可以跳过，不会锁住已经熟悉产品的用户。引导阶段、教程任务和成就解锁时间只保存在本机，不进入项目文件、模型上下文或网络请求。

皮肤选择和降低动效同样只保存在桌面 WebView 本机。实验室、论文纸、深夜观测站、高对比和跟随系统始终可用；完成官方科研协作教程后会解锁装饰性皮肤 Origin Ring。亮色、暗色与高对比等基础可访问性选项不会被成就锁定。

DeepSeek 官方预设使用 `https://api.deepseek.com`，可选择 `deepseek-v4-pro` 或 `deepseek-v4-flash`。预设只修改 Base URL 和模型名，不读取或覆盖 API Key；申请、充值、Key 管理和文档按钮通过受限的桌面权限交给系统浏览器，只允许打开 DeepSeek 官方域名。模型和价格可能变化，请以按钮打开的官方页面为准。

关闭主窗口会停止随应用启动的本地后端并退出。安装器、升级和卸载不会主动删除用户数据。

0.1.x 便携版用户可以在桌面版设置页选择「导入旧版便携包数据」。导入只复制旧目录的 `data/` 和 `config/.env`，不会修改旧目录，也不会覆盖已有的桌面版数据。

## 项目与会话

- 同一时间只有一个活动项目；切换项目时会加载该项目的会话、文件树和工作记忆。
- 新项目或切换项目时文件夹默认折叠；用户手动展开后，工具刷新文件树只保留仍然存在的展开目录。
- 会话列表和消息接口默认只加载最新 60 条，完整历史仍保存在本地 JSONL 中。
- 会话删除是软删除；原始 JSONL 历史保留在数据目录。
- 移除项目只取消 Workmode Public 中的注册关系，绝不会删除硬盘中的项目文件。
- 项目内新注册的子目录会显示在最近的已注册父项目下，同级项目按名称排列。

### 官方教程项目

左侧「创建教程项目」会让用户选择一个父目录，然后把安装包内的初始教程复制为独立项目并自动注册。教程包含真实开放获取 PDF、模拟实验数据、预计算事实报告、EPR 格式示例和项目级 `WORKMODE.md` 主持协议。

教程任务卡根据真实产品事件自动推进：打开 PDF、发送首个任务、完成网页检索、运行项目分析脚本、保存 Markdown 和查看上下文。任务按钮可以高亮操作区域或把建议指令填入输入框，但不会替用户自动发送消息。六项完成后显示正式项目入口并解锁「科研协作入门」成就。

只有通过应用创建、同时具有本地注册记录和有效 `WORKMODE_TUTORIAL.json` 标识的官方教程才显示「重置教程」。重置前会把完整项目目录、项目 Work Memory、结构化项目记忆和当前计划备份到 `%LOCALAPPDATA%\WorkmodePublic\data\work\tutorial-backups\`；随后恢复内置模板、软删除旧会话并新建空白会话。普通项目即使复制同名标识也不能调用该操作。

「重置教程」会清空六项教程任务进度，但不会抹掉已经解锁的历史成就；成就代表用户曾经完成过真实操作，不是教程文件状态。

## 文件与模型工具

模型直接加载必要工具，不依赖动态工具搜索：

- `project_list_dir`：列出一层目录；
- `project_glob`：按 pattern 查找文件；
- `project_grep`：用正则搜索 UTF-8 文本；
- `project_read`：按行号读取 UTF-8 文件；
- `project_write`：创建或整体重写文本文件；
- `project_edit`：对已有文本做精确字符串替换；
- `project_bash`、`project_python`：在当前项目根目录运行带超时和输出截断的命令或小型 Python 代码；
- `project_python_file`：使用安装包自带的 Python 直接运行项目内已有 `.py` 脚本，不要求用户另装 Python；
- `web_search`、`web_fetch`：并行检索和读取公开 HTTP(S) 文本资源；
- `memory_write`、`memory_read`、`memory_list`：维护项目或全局工作记忆；
- `plan_my_steps`、`mark_step_done`：维护当前任务计划。

文件工具只接受当前项目中的相对路径，并拒绝越界路径、依赖/缓存目录和 `.env` 等敏感配置。命令工具不是系统级强沙箱，请只注册可信项目，并在重要修改后检查 diff 和测试结果。

## 固定上下文与工作记忆

项目根目录存在 `WORKMODE.md` 时，它会作为该项目专属 system prompt 在每一轮自动加载，并支持用独占一行的 `@相对路径` 展开项目内 UTF-8 文本。这个入口适合放项目纪律、教学主持协议等必须强制生效且应随项目一起分发的规则；它只影响当前项目，不会写入基础提示词、全局记忆或其它项目。

项目工作记忆、结构化工作记忆的索引和正文、当前计划都会固定进入 system prompt。若项目协议保存在文件中，可以在项目工作记忆里独占一行写：

```md
@docs/protocol.md
@INSTRUCTIONS.md
```

下一轮请求会从当前项目根目录读取这些 UTF-8 文本并注入上下文。绝对路径、越界路径、二进制文件和循环引用会显示为导入警告。

## 上下文窗口与压缩

完整会话历史包含用户消息、助手文字、工具调用和工具结果。模型侧不会无条件装入全部历史：

1. 先计算 system prompt、固定导入、工作记忆、计划和工具 schema；
2. 从配置的 Context Budget 中扣除这些固定部分；
3. 从最近历史向前选择能够完整装入的合法消息后缀，避免孤立工具结果；
4. 在顶部 token 条显示估算占用、已包含/丢弃的历史数量、固定文件和摘要状态。

点击「压缩上下文」会生成 `<CONTEXT_SUMMARY>` 标记。后续模型从最新标记继续，但标记之前的原始 JSONL 仍保留，压缩不是删除历史。

## 本地数据与安全边界

正式桌面版把用户状态保存在：

```text
%LOCALAPPDATA%\WorkmodePublic\
  config\.env        模型 API 与本地配置
  data\              项目注册、会话、记忆、计划和历史修复备份
  logs\              桌面后端日志
```

官方教程重置备份位于 `data\work\tutorial-backups\<project-slug>\`，不会混入用户选择的教程工作目录。

默认后端只绑定 loopback。PDF/图片预览使用扩展名、大小与 magic bytes 白名单；网页工具拒绝 loopback、内网、链路本地地址、非常用端口和非 HTTP(S) 协议，并在每次重定向后重新验证目标。

Tauri 更新签名用于验证下载的更新内容，但当前安装器尚未配置 Windows Authenticode，因此首次下载仍可能触发 SmartScreen 提示。

## 开发与发行

仓库目录：

```text
backend/             FastAPI、上下文、会话、工具和文件存储
frontend/            React + Vite 工作台
desktop/             Tauri 2 桌面壳、后端生命周期和 NSIS 配置
tutorial-project/    随安装包分发的官方教程初始模板
scripts/             源码启动、验证和桌面发行脚本
docs/                架构、开发、发行与产品路线图
```

- [开发环境与测试](docs/DEVELOPMENT.md)
- [当前架构](docs/ARCHITECTURE.md)
- [桌面发行与自动更新](docs/DESKTOP-DISTRIBUTION.md)
- [产品路线图](docs/PRODUCT-ROADMAP.md)

GitHub Actions 是正式 Windows Release 的唯一主发行路径；发布环境固定使用 Node.js 22 与 npm 10.9.4，并通过 lockfile 做干净安装。早期 0.1.x 便携包构建器已经退役。旧版数据导入能力继续保留，用于非破坏性迁移。

## 当前边界

- 正式安装包目前只发布 Windows x64；
- `project_bash`、`project_python` 和 `project_python_file` 有项目 cwd、超时、输出截断和取消能力；shell 另有破坏性命令黑名单，但这些工具都不是 OS 级隔离；
- 网络工具提供基础公开网页检索与抓取，还不是带 DOI 去重、引文管理和全文获取的完整文献流水线；
- 尚未提供子 agent；需要先确定权限、并发、预算、取消和文件冲突语义；
- 尚未配置 Windows Authenticode。

## License

[MIT](LICENSE)
