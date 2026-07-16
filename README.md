# Workmode Public

> 让 AI 在真实科研项目里工作，而不只是停留在聊天框里。

Workmode Public 是一个可独立安装、本地优先的科研工作台。它把项目文件、论文阅读、AI 工具执行、会话历史和长期工作上下文放在同一个桌面应用中，面向真实科研工作，而非人格陪伴或生活记忆。

当前正式支持 **Windows x64**。安装版已包含运行环境，普通用户不需要预装 Node.js、Python 或 Rust。

[下载最新版本](https://github.com/carbocation123/workmode-public/releases/latest) · [查看更新记录](https://github.com/carbocation123/workmode-public/releases) · [开发文档](docs/DEVELOPMENT.md) · [反馈问题](https://github.com/carbocation123/workmode-public/issues) · [安全策略](SECURITY.md)

## 为什么是 Workmode Public

- **围绕真实项目工作**：AI 可以在用户授权的项目目录中读取、搜索、创建和精确编辑文件，而不是把所有材料复制进一个封闭知识库。
- **科研过程可追踪**：会话、工具调用、停止状态、上下文压缩和项目记忆都有明确记录；压缩上下文不会删除原始历史。
- **本地数据由用户控制**：项目、论文、会话、配置和诊断报告保存在本机；只有用户主动使用的模型、MinerU、网页或更新功能会产生对应网络请求。
- **开箱即用的桌面体验**：提供 Windows 安装包、首次使用向导、应用内更新和一键错误报告，不要求用户自行配置开发环境。

## 两种工作方式

| 模式 | 适合谁 | 主要能力 |
| --- | --- | --- |
| **科研工作台** | 需要完整项目控制和可组合 AI 工具的用户 | 项目与会话、文件树、Markdown/PDF/图片预览、受控文件编辑、Shell/Python、网页检索、项目记忆、上下文查看与压缩 |
| **文献智库** | 希望快速建立本地论文库并围绕文献对话的用户 | PDF 入库与去重、论文选择、原文阅读、标签与笔记、多会话、回收站、可选 MinerU 增强解析和跨文献协作 |

两个模式共享同一套项目注册、会话历史、模型配置、上下文机制和桌面安全边界，可以随时返回功能大厅切换。

## 核心能力

### 项目化 AI 工作

- 注册和切换多个本地项目，并按真实父子目录关系展示项目。
- 每个项目拥有独立会话、项目工作记忆、任务计划和上下文状态。
- 模型可调用受控工具读取、搜索、创建和编辑项目文件，也可在项目目录运行带超时、取消和输出限制的 Shell/Python。
- 文件查看器支持 UTF-8 文本、Markdown、PDF 和常见图片；编辑已有 Markdown 时使用内容版本校验，避免覆盖外部修改。

### 长期上下文与可追踪历史

- 使用 `@相对路径.md` 将项目协议、实验约束或其它 UTF-8 文本固定注入上下文。
- 按 token 预算动态选择最近历史，并在界面显示历史消息、固定文件和摘要占用。
- 手动压缩上下文时生成明确的摘要续接点，完整 JSONL 历史仍然保留。
- AI 回复、工具开始、工具结果和中途停止产生的内容按真实到达顺序持久化。

### 本地文献工作流

1. 只填写名称即可创建文献项目。Windows 有 D 盘时默认保存在 `D:\workmode\<项目名>`，否则使用 `~/workmode`；旧版外部路径项目仍可继续使用。
2. 拖入 PDF 后先检查文件清单，只有点击“确认入库”才写入项目，并使用 SHA-256 去重。
3. 入库不会自动选择论文、调用模型或启动 MinerU。用户可以选择论文或笔记作为当前对话资料，再自然语言提问。
4. 普通阅读优先使用已有解析文本，否则直接读取 PDF 文本层；只有用户明确要求增强解析、事实抽取或归档时才调用 MinerU 流程。
5. 论文记录、PDF 和解析产物可以整体移入项目回收站并无覆盖恢复；历史会话不会被改写。

## 三分钟开始

1. 从 [GitHub Releases](https://github.com/carbocation123/workmode-public/releases/latest) 下载 `workmode-public-<version>-windows-x86_64-setup.exe`。
2. 安装并启动 Workmode Public，在功能大厅选择“科研工作台”或“文献智库”。
3. 在首次向导中填写 OpenAI-compatible Base URL、模型名和 API Key；也可以使用内置的 DeepSeek 配置引导。
4. 创建教程项目、打开自己的项目，或新建一个本地文献库。
5. 根据界面引导开始对话、阅读文件、导入论文或调用工具。所有向导都可以跳过，也可以稍后在设置中重新播放。

模型工具循环没有固定轮数上限。它会持续到模型给出最终正文、用户点击停止，或发生无法继续的错误；普通工具失败会返回给模型，由模型决定修正参数、改用其它方法或向用户说明。

## 本地优先与数据边界

正式桌面版默认将状态保存在：

```text
%LOCALAPPDATA%\WorkmodePublic\
  config\.env          模型 API 与本地配置
  data\                项目注册、会话、记忆、计划和历史备份
  logs\runs\<run-id>  最近 20 次桌面运行日志
  reports\             用户主动生成的错误报告 ZIP
```

| 数据或行为 | 默认边界 |
| --- | --- |
| 项目文件、PDF、会话、记忆和计划 | 保存在本机，不由应用自动上传 |
| 模型对话 | 仅在用户发送消息时请求用户配置的模型服务；请求会包含完成当前任务所需的上下文 |
| MinerU | 可选；仅在用户明确要求增强解析时使用配置的 MinerU 服务 |
| 网页检索 | 仅在模型调用网页工具时访问公开 HTTP(S) 页面 |
| 运行日志与错误报告 | 保存在本机；报告 ZIP 由用户主动生成和发送，应用不会自动上传或删除 |
| 应用更新 | 用户检查更新时访问 GitHub Releases，下载内容经过 Tauri 更新签名验证 |

默认后端只绑定 loopback。PDF 和图片预览使用扩展名、大小与 magic bytes 白名单；网页工具拒绝 loopback、内网、链路本地地址、非常用端口和非 HTTP(S) 协议，并在重定向后重新验证目标。

设置页的“一键生成错误报告”只收集本次桌面运行日志，限制单项日志尾部大小，并再次脱敏 Token、API Key、密码和 Windows 本地路径。生成后，Windows 文件管理器会定位 ZIP，是否发送以及何时删除都由用户决定。

## 从源码运行

最简单的浏览器源码入口：

```powershell
git clone https://github.com/carbocation123/workmode-public.git
cd workmode-public
.\start-workmode-public.cmd
```

停止源码后端：

```powershell
.\stop-workmode-public.cmd
```

源码启动器会按需创建 Python 虚拟环境、安装依赖、构建前端、启动本地后端并打开浏览器。Tauri 桌面开发、测试矩阵和正式发行步骤见 [开发环境与测试](docs/DEVELOPMENT.md) 与 [桌面发行与自动更新](docs/DESKTOP-DISTRIBUTION.md)。

## 文档

| 文档 | 内容 |
| --- | --- |
| [开发环境与测试](docs/DEVELOPMENT.md) | 本地启动、依赖、测试命令和仓库维护 |
| [当前架构](docs/ARCHITECTURE.md) | 前后端、桌面壳、数据流和安全边界 |
| [桌面发行与自动更新](docs/DESKTOP-DISTRIBUTION.md) | Windows 构建、签名、安装包和更新流程 |
| [特化模块开发规范](docs/SPECIALIZED-MODULES.md) | 文献智库等特化 Workmode 的共享内核约束 |
| [官方签名皮肤](docs/CUSTOM-SKINS.md) | `.workmode-skin` 协议、验签和安全恢复 |
| [产品路线图](docs/PRODUCT-ROADMAP.md) | 已完成能力、当前边界与后续方向 |

## 当前边界

- 正式安装包目前只发布 Windows x64。
- 项目 Shell/Python 工具有工作目录、超时、输出截断、取消和危险命令限制，但不是操作系统级沙箱。
- 文献智库仍缺真实 MinerU 联网验收、DOI 级语义去重、候选标签治理和研究论文/综述最终主档生成。
- 尚未提供子 agent；需要先明确权限、并发、预算、取消和文件冲突语义。
- Tauri 更新内容经过签名验证，但 Windows 安装器尚未配置 Authenticode，首次下载可能触发 SmartScreen 提示。

## 反馈与安全

- 一般问题和功能建议：[GitHub Issues](https://github.com/carbocation123/workmode-public/issues)
- 版本下载与更新说明：[GitHub Releases](https://github.com/carbocation123/workmode-public/releases)
- 安全问题：[SECURITY.md](SECURITY.md)
- 应用运行错误：在“设置 → 桌面应用与支持”生成脱敏 ZIP，再通过用户选择的渠道发送

## License

[MIT](LICENSE) © 2026 Jason Yang
