# Workmode Public

Workmode Public 是一个可独立安装的纯净科研工作助手。

[下载最新版](https://github.com/carbocation123/workmode-public/releases/latest) · [查看源代码](https://github.com/carbocation123/workmode-public)

它不加载伴侣人格或生活记录等私人模块，专注于科研项目、文档和可追踪的工作上下文。当前版本保留这些核心能力：

- 项目注册与会话存储；
- 项目按本地目录父子关系分层展示；
- 停止正在生成的回复和工具链；
- 会话重命名、会话归档与项目安全移除；
- 最近 60 条会话加载；
- 项目工作记忆；
- `@相对路径.md` 固定注入上下文；
- 手动压缩上下文；
- token 预算动态历史窗口与上下文面板；
- 原生文件夹选择器（失败时仍可手输绝对路径）；
- Markdown 渲染与编辑；
- UTF-8 文本预览；
- PDF/图片安全白名单预览；
- 模型可调用的工作工具：读文件、写文件、精确编辑、列目录、glob 找文件、grep 搜内容、运行 shell / Python、工作记忆、任务计划；
- OpenAI-compatible 流式聊天。

## 目录

```text
workmode-public/
  backend/     FastAPI 后端
  frontend/    React + Vite 前端
  scripts/     本地开发启动脚本
  docs/        架构和分发说明
```

## 正式桌面版（Windows）

普通用户只需要双击安装包：

```text
workmode-public-0.2.0-windows-x86_64-setup.exe
```

安装包可从 [GitHub Releases](https://github.com/carbocation123/workmode-public/releases/latest) 获取。

目标电脑不需要安装 Node.js、Python 或 Rust。安装后从开始菜单启动；关闭窗口即停止本地后端并退出，更新在应用内“设置 → 桌面应用”完成。用户配置、项目注册、会话和工作记忆保存在 `%LOCALAPPDATA%\WorkmodePublic`，升级或卸载程序文件不会把它们混进安装目录。

0.1.x 便携包用户可在首次启动后的设置页选择“导入旧版便携包数据”。导入只复制 `data/` 与 `config/.env`，不会改动旧目录。

桌面版构建、签名和发布方法见 [docs/DESKTOP-DISTRIBUTION.md](docs/DESKTOP-DISTRIBUTION.md)。

## 一键启动（Windows）

这是源码/开发目录的一键启动器，会使用本机 Python 和 Node 来安装依赖、构建前端；普通用户不需要使用这一入口。

双击：

```text
start-workmode-public.cmd
```

它会自动做这些事：

1. 如果 `.env` 不存在，从 `.env.example` 复制一份；
2. 创建 `backend/.venv`；
3. 安装后端依赖；
4. 安装前端依赖；
5. 构建前端 `dist`；
6. 启动本地后端；
7. 打开浏览器。

后端默认访问地址：

```text
http://127.0.0.1:8765
```

停止服务：

```text
stop-workmode-public.cmd
```

日志位置：

```text
logs/
```

如果你已经安装好依赖，只想启动而不允许脚本自动安装：

```powershell
.\start-workmode-public.cmd -NoInstall
```

如果改了前端代码，需要强制重新构建：

```powershell
.\start-workmode-public.cmd -RebuildFrontend
```

## 构建分发包（给其他电脑用）

在源码目录运行：

```powershell
.\scripts\build-release.ps1
```

默认输出：

```text
release/workmode-public-0.1.3-win-x64/
release/workmode-public-0.1.3-win-x64.zip
release/workmode-public-0.1.3-win-x64.zip.sha256
release/manifest-0.1.3.json
```

分发包目录里给用户双击：

```text
WorkmodePublic.cmd
```

停止：

```text
StopWorkmodePublic.cmd
```

运行配置在：

```text
config/.env
```

用户数据在：

```text
data/
```

日志在：

```text
logs/
```

发行包会包含已构建前端和 Python runtime；目标电脑不需要 Node。构建脚本默认复制 `backend/.venv` 与构建机 Python base runtime，适合先做 Windows x64 便携包。正式公开发布时，建议在固定 CI/打包机上构建，或传入经过验证的 portable Python runtime：

```powershell
.\scripts\build-release.ps1 -RuntimeSource C:\Python314
```

如果只想生成不带 runtime 的调试包：

```powershell
.\scripts\build-release.ps1 -NoRuntime
```

## 更新分发包

普通用户升级已有版本：

```text
1. 下载新版 zip
2. 解压新版 zip
3. 双击新版目录里的「升级已有版本.cmd」
4. 在弹窗中选择旧版 Workmode Public 文件夹
5. 等提示“升级完成”
6. 确认新版能打开、项目和会话都在之后，可以删除旧版文件夹
```

这个迁移式升级不会修改旧版目录；新版目录会成为后续继续使用的目录。它会迁移：

- `config/.env`（模型 API 配置）
- `data/`（项目、会话、工作记忆等用户数据）

并保留新版自带的：

- `app/`
- `runtime/`
- `config/.env.example`

技术用户也可以使用原地更新入口：

```text
UpdateWorkmodePublic.cmd
```

用本地 zip 更新：

```powershell
.\UpdateWorkmodePublic.cmd -PackagePath D:\downloads\workmode-public-0.1.3-win-x64.zip -Sha256 <zip-sha256>
```

用远程 manifest 更新：

```powershell
.\UpdateWorkmodePublic.cmd -ManifestUrl https://example.com/releases/manifest.json
```

原地更新器只替换 `app/`，并保留：

- `config/`
- `data/`
- `logs/`
- `runtime/`

更新前会把旧 `app/` 移到 `backups/`。如果安装新 `app/` 失败，会尝试回滚旧版本。

## 手动启动（开发版）

1. 复制配置：

```powershell
Copy-Item .env.example .env
```

2. 填写模型配置：

```text
WORKMODE_MODEL_BASE_URL=https://api.deepseek.com/v1
WORKMODE_MODEL_NAME=deepseek-v4-pro
WORKMODE_MODEL_API_KEY=你的 key
```

3. 安装并启动后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

4. 启动前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

## 模型 API 设置

前端左下角点击「设置」后，可以在「模型 API」里填写：

- Base URL，例如 `https://api.deepseek.com/v1`；
- Model Name，例如 `deepseek-v4-pro`；
- API Key；
- Context Budget；
- Timeout 秒数。

保存后配置会写入本地 `.env`，下一轮聊天请求立即生效；API Key 不会从后端回显到前端。

## 安全默认值

- 默认绑定 `127.0.0.1`，不建议改成 `0.0.0.0`。
- 文件预览使用扩展名白名单、UTF-8 校验、PDF/图片 magic bytes 校验。
- 模型文件工具锁定当前项目根目录；拒绝绝对路径、越界路径、缓存/依赖目录和 `.env` 等敏感配置文件。
- `project_bash` / `project_python` 在当前项目根目录运行，带超时、输出截断和破坏性命令黑名单。
- `web_search` / `web_fetch` 只访问公开 HTTP(S) 文本资源，拒绝本机、内网和非常用端口，并限制重定向与响应体大小。
- Markdown 编辑只允许修改已存在的 `.md` / `.markdown` 文件，并使用 hash 版本检查避免覆盖外部修改。
- 如果设置 `WORKMODE_PUBLIC_TOKEN`，所有 `/api` 请求都需要 `X-Workmode-Token`。

## 模型项目工具

聊天模型会直接加载必要工作工具，不使用 `search_my_tools` 动态搜索。

项目内文件/执行工具：

- `project_list_dir`：列出一层目录；
- `project_glob`：按 pattern 查找文件；
- `project_grep`：按正则搜索文本内容；
- `project_read`：按行号读取 UTF-8 文本文件；
- `project_edit`：对已有文本文件做精确字符串替换；
- `project_write`：新建或整体重写文本文件；
- `project_bash`：在项目根目录运行 shell 命令；
- `project_python`：在项目根目录运行 Python 代码。

网络研究工具：

- `web_search`：一次并行执行 1–5 个检索词，每个检索词最多返回 8 条结果；
- `web_fetch`：一次并行读取 1–4 个公开 HTTP(S) 文本页面，用于核对原始来源正文。

基础检索不需要用户额外配置搜索 API Key。网页内容一律按不可信外部资料处理，不能覆盖系统规则或指挥模型泄露配置、继续调用工具。

项目工具路径都相对当前项目根目录解析。一次工具调用会在聊天区显示为一张紧凑卡片，运行、完成、失败或已取消状态原位更新；如果工具修改了文件，前端会在本轮结束后刷新文件树和当前打开文件。聊天区在读者位于底部附近时自动跟随新消息；主动向上滚动后会暂停跟随并显示「回到最新」。模型工具循环没有固定轮数上限，会持续到模型给出最终正文、用户点击停止，或模型/网络/工具错误结束。

工作记忆和计划工具：

- `memory_write` / `memory_read` / `memory_list`：维护工作记忆；
- `plan_my_steps` / `mark_step_done`：维护当前任务计划。

工作记忆采用“索引 + 正文固定注入”：每轮 prompt 会看到记忆名、类型、描述和正文；`memory_read` 仍保留，用于需要逐字确认或刷新某条记忆时重读。

## 上下文窗口与压缩

Workmode Public 采用动态预算上下文策略：

- JSONL 会保存完整会话历史，包括用户消息、助手消息、工具调用和工具结果；
- 启动时会检查旧版本留下的悬空工具调用；修复前先备份原 JSONL/元数据到 `%LOCALAPPDATA%\WorkmodePublic\backups\history-repair\`，再把缺失结果标记为「已取消」。迁移可重复运行且不会改写已有成功/失败结果；旧版未曾保存的文字分段不会凭猜测重建；
- 模型侧不会无脑加载全部历史；
- 每轮会先扣除 system prompt、工具 schema、固定导入和工作记忆的 token；
- 剩余预算从最近历史向前动态装载；
- 历史工具调用结果只在预算允许且能保持调用链完整时进入上下文；
- 如果较早历史被省略，上下文条会显示历史 included/dropped；
- 点击「压缩上下文」会插入一条 `<CONTEXT_SUMMARY>` marker，后续模型从最近 marker 起续接；
- 压缩不会删除原始 JSONL 历史，只是改变模型可见的续接起点。

压缩摘要采用 8 段结构：

1. 主要请求与意图；
2. 关键技术概念；
3. 文件与代码段；
4. 错误与修复；
5. 问题解决过程；
6. 所有用户消息；
7. 待办与未完成；
8. 当前工作与下一步。

## 固定上下文用法

在“工作记忆”里写独占一行：

```md
@docs/protocol.md
@README.md
```

下一轮聊天时，后端会从当前项目根目录读取这些 UTF-8 文本文件并注入 system prompt。绝对路径、越界路径、二进制文件和循环引用会变成可见警告。

## 打开项目文件夹

在左侧「项目」面板点击 `+`，可以：

- 点 `📁` 弹出系统文件夹选择器；
- 或手动输入绝对路径。

文件夹选择器由本地后端调用原生 tkinter 对话框完成，因此需要运行在有桌面的本机环境。远程、容器或无 GUI 环境下会提示失败，此时手输路径即可。

## 项目和会话管理

- 如果新打开的文件夹位于某个已注册项目目录内部，它会自动显示在最近的父项目下方；同级项目按名称排列，不再按建立先后堆叠。
- 会话名称可以双击修改，也可以点击右侧编辑按钮。
- 生成过程中，发送按钮会变成「停止」。停止后不会继续发起工具轮次；已经生成的文字按原始“文字 → 工具 → 文字”顺序保留，正在执行但尚未返回的工具会标记为「已取消」。
- 删除会话采用本地软删除，原始 JSONL 历史仍保留在数据目录中。
- 移除项目只删除 Workmode Public 中的注册关系；确认框会展示项目路径，硬盘中的项目文件绝不会被删除。

## 当前边界

这是可安装、可在应用内检查 GitHub Release 更新的本地优先版本。

- `project_bash` / `project_python` 已开放；它们不是系统级沙盒，只做项目 cwd、超时、输出截断和黑名单防护。
- 桌面版已有托盘、Tauri 更新签名和应用内检查更新；Windows Authenticode 代码签名仍未配置，因此新安装包可能触发 SmartScreen 提示。
- 本地 token 是可选项；真正公开网络部署必须加完整鉴权。
