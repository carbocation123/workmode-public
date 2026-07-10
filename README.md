# Workmode Public

Workmode Public 是一个可独立安装、本地优先的纯净科研工作助手。它围绕项目文件、科研写作、实验记录、数据处理和可追踪的长期工作上下文设计，不包含私人伴侣、生活记忆或人格关系模块。

[下载最新 Windows 版本](https://github.com/carbocation123/workmode-public/releases/latest) · [查看发行记录](https://github.com/carbocation123/workmode-public/releases) · [报告安全问题](SECURITY.md)

## 主要能力

- 注册并切换多个本地项目，按真实父子目录关系展示项目；
- 为每个项目保存独立会话、项目工作记忆和任务计划；
- 浏览项目文件树，预览 UTF-8 文本、Markdown、PDF 和常见图片；
- 渲染及编辑已有 Markdown 文件，使用内容版本校验避免覆盖外部修改；
- 让模型读取、搜索、创建和精确编辑项目文件，也可以在项目目录运行受限的 shell 与 Python；
- 使用 `web_search` 并行检索公开网页，再用 `web_fetch` 核对原始页面；
- 在工作记忆中用 `@相对路径.md` 固定注入项目协议或其他 UTF-8 文本；
- 按 token 预算动态选择最近历史，并在界面显示估算总量、历史数量、固定导入文件数和摘要状态；
- 手动压缩上下文，保留完整 JSONL 历史，只改变后续模型的续接起点；
- 停止正在运行的生成和工具链，并按原始“文字 → 工具 → 文字”顺序持久化已产生内容；
- 从 GitHub Releases 检查、下载并安装经过 Tauri 更新签名验证的新版本。

模型工具循环没有固定轮数上限。它会持续到模型给出最终正文、用户点击停止，或发生无法继续的模型/网络错误；普通工具失败会作为结果返回模型，由模型决定修正参数、换方法或向用户说明。

## 安装与首次使用

当前正式分发目标是 Windows x64。普通用户只需要从 [Releases](https://github.com/carbocation123/workmode-public/releases/latest) 下载：

```text
workmode-public-<version>-windows-x86_64-setup.exe
```

目标电脑不需要安装 Node.js、Python 或 Rust。安装完成后：

1. 从开始菜单启动 Workmode Public；
2. 打开「设置 → 模型 API」，填写 OpenAI-compatible Base URL、模型名和 API Key；
3. 在左侧项目栏添加一个本地文件夹；
4. 新建会话并开始工作，`Ctrl+Enter` 发送，`Enter` 换行；
5. 后续在「设置 → 桌面应用」检查并安装更新。

关闭主窗口会停止随应用启动的本地后端并退出。安装器、升级和卸载不会主动删除用户数据。

0.1.x 便携版用户可以在桌面版设置页选择「导入旧版便携包数据」。导入只复制旧目录的 `data/` 和 `config/.env`，不会修改旧目录，也不会覆盖已有的桌面版数据。

## 项目与会话

- 同一时间只有一个活动项目；切换项目时会加载该项目的会话、文件树和工作记忆。
- 会话列表和消息接口默认只加载最新 60 条，完整历史仍保存在本地 JSONL 中。
- 会话删除是软删除；原始 JSONL 历史保留在数据目录。
- 移除项目只取消 Workmode Public 中的注册关系，绝不会删除硬盘中的项目文件。
- 项目内新注册的子目录会显示在最近的已注册父项目下，同级项目按名称排列。

## 文件与模型工具

模型直接加载必要工具，不依赖动态工具搜索：

- `project_list_dir`：列出一层目录；
- `project_glob`：按 pattern 查找文件；
- `project_grep`：用正则搜索 UTF-8 文本；
- `project_read`：按行号读取 UTF-8 文件；
- `project_write`：创建或整体重写文本文件；
- `project_edit`：对已有文本做精确字符串替换；
- `project_bash`、`project_python`：在当前项目根目录运行带超时和输出截断的命令；
- `web_search`、`web_fetch`：并行检索和读取公开 HTTP(S) 文本资源；
- `memory_write`、`memory_read`、`memory_list`：维护项目或全局工作记忆；
- `plan_my_steps`、`mark_step_done`：维护当前任务计划。

文件工具只接受当前项目中的相对路径，并拒绝越界路径、依赖/缓存目录和 `.env` 等敏感配置。命令工具不是系统级强沙箱，请只注册可信项目，并在重要修改后检查 diff 和测试结果。

## 固定上下文与工作记忆

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

默认后端只绑定 loopback。PDF/图片预览使用扩展名、大小与 magic bytes 白名单；网页工具拒绝 loopback、内网、链路本地地址、非常用端口和非 HTTP(S) 协议，并在每次重定向后重新验证目标。

Tauri 更新签名用于验证下载的更新内容，但当前安装器尚未配置 Windows Authenticode，因此首次下载仍可能触发 SmartScreen 提示。

## 开发与发行

仓库目录：

```text
backend/             FastAPI、上下文、会话、工具和文件存储
frontend/            React + Vite 工作台
desktop/             Tauri 2 桌面壳、后端生命周期和 NSIS 配置
scripts/             源码启动、验证和桌面发行脚本
docs/                架构、开发、发行与产品路线图
```

- [开发环境与测试](docs/DEVELOPMENT.md)
- [当前架构](docs/ARCHITECTURE.md)
- [桌面发行与自动更新](docs/DESKTOP-DISTRIBUTION.md)
- [产品路线图](docs/PRODUCT-ROADMAP.md)

GitHub Actions 是正式 Windows Release 的唯一主发行路径；早期 0.1.x 便携包构建器已经退役。旧版数据导入能力继续保留，用于非破坏性迁移。

## 当前边界

- 正式安装包目前只发布 Windows x64；
- `project_bash` 和 `project_python` 有项目 cwd、超时、输出截断和破坏性命令黑名单，但不是 OS 级隔离；
- 网络工具提供基础公开网页检索与抓取，还不是带 DOI 去重、引文管理和全文获取的完整文献流水线；
- 尚未提供子 agent；需要先确定权限、并发、预算、取消和文件冲突语义；
- 尚未配置 Windows Authenticode。

## License

[MIT](LICENSE)
