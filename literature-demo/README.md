# Workmode 文献特化模块

文献项目使用正式 Workmode 的项目注册、session、JSONL、流式工具循环、上下文窗口、压缩、停止和项目记忆。活动前端已经迁入 `frontend/src/literature/` 并进入正式桌面构建；本目录只保留固定项目模板、领域说明和退役原型归档。

## 当前结构

```text
literature-demo/
  project-template/            literature-library 固定结构模板
  archive/
    standalone-backend-2026-07-13/  不进入运行时的旧纵切后端
    standalone-frontend-dev-shell-2026-07-13/  退役的 5176 Vite 壳与启动器
```

正式运行代码位于：

- `backend/app/literature_project.py`：项目识别、固定结构、12 个文献工具和原子写入；标签更新前可先用 `literature_tag_list` 读取规范注册表；
- `backend/app/literature_pipeline.py`：MinerU、首页元数据、标准命名和六段事实报告；
- `backend/app/literature_routes.py`：固定项目文件到文献前端的投影 API；
- `backend/app/routes.py`、`llm.py`、`prompt.py`：正式 Workmode session、chat、工具画像和上下文。
- `frontend/src/literature/`：正式文献列表、标签、对话、详情、PDF 与笔记界面；
- `frontend/literature/index.html`：主 Vite 工程的文献页面入口。

## 当前可体验内容

- 使用正式 Workmode 多 session，对话只回放最新 60 条消息；顶部项目名和上下文百分比读取真实项目与 context API；
- 用户消息立即显示，AI 正文增量、工具开始与结果按真实 SSE 顺序更新；工具开始/结果继续写入正式 JSONL，并按 `tool_call_id` 合并成一张工具卡，完成后回读 session 校准；
- 文献卡片、标签、详情、完整客观事实和原始 PDF 直接读取项目文件；
- 拖入 PDF 后先显示确认清单；确认后才流式写入 `papers/unprocessed/pdf/`，校验 PDF 头并按 SHA-256 去重；成功论文自动加入当前 session，并以不可见 `literature_import_confirmed` 系统事件进入模型上下文；
- 勾选文献或笔记后随下一条用户消息写入 `meta.active_context`，只表示本轮当前资料，不是权限；
- 文献项目只加载 `literature_*` 工具，不加载 Shell、Python、通用文件、Web、通用 memory 或 plan；
- 标签、关注点、摘要、跨文献段和笔记工具直接写入，不存在 proposal、confirm/reject 或 `confirmed` 参数；
- `literature_process` 在正式工具调用中运行 MinerU、元数据识别、标准命名和事实报告，停止对话会传入取消事件；前端不再维护独立任务轮询；
- 上下文整理调用正式 Workmode compactor，不删除原始 JSONL；
- 项目记忆按钮读取正式 Workmode 项目 memory，不维护第二份记忆。

## 固定项目结构

功能大厅没有找到已注册的文献项目时，会提示用户选择或新建一个空文件夹，并在其中建立模板结构、注册项目和创建第一个正式 session。完整工作台不再重复提供文献入口。模板见 `project-template/`，运行时初始化器会创建同样的内容：

```text
literature-project/
  literature-project.json
  WORKMODE.md
  LITERATURE_PROJECT.md
  README.md
  catalog.json
  tags.json
  processed-index.md
  papers/
    README.md
    unprocessed/pdf/
    unprocessed/extracted/<paper-id>/
    processed/pdf/
    processed/extracted/<paper-id>/
  notes/README.md
  exports/
```

`catalog.json` 和 `tags.json` 是机器权威源。通用 Markdown 编辑接口在文献项目里只允许修改既有 `notes/*.md`；其他受管文件只能通过领域服务变化。

## 本机配置

模型复用 Workmode 本机配置。MinerU 只从本机环境读取，不写入项目或仓库：

```dotenv
WORKMODE_MINERU_API_KEY=
WORKMODE_MINERU_MODEL_VERSION=pipeline
WORKMODE_MINERU_LANGUAGE=en
WORKMODE_MINERU_TIMEOUT_SECONDS=180
```

超时允许 60–1800 秒。元数据只取 PDF 首页 `Cite This`；ACS/Elsevier 页眉被过滤时读取现有 `layout.json` DOI 邻近块，不根据原文件名或搜索摘要猜测。

## 启动与入口

正式桌面应用启动后先显示功能大厅：「科研工作台」进入完整 Workmode，「文献智库」进入本模块。首次进入文献智库时选择一个空文件夹；后续会优先恢复当前或最近使用的文献项目。文献页和完整工作台使用相同的左侧活动栏：顶部返回功能大厅，底部打开共享全局设置；设置页再次点击底部按钮可返回文献智库。文献顶栏不再重复显示连接状态或特化模式标签。

点击文献卡片、项目笔记或项目记忆时，内容在脱离主页面网格的中央模态窗口打开。文献详情的「原始 PDF」页签读取 catalog 中的项目相对路径，并复用完整工作台的 `PdfViewer` 与 `/fs/media` 端点；阅读器先在应用内获取 PDF，再以短生命周期 `blob:` URL 显示，防止第三方下载接管程序把阅读操作改成下载。

源码开发时只启动主前端：

```powershell
npm --prefix frontend run dev
```

功能大厅地址是 `http://127.0.0.1:5173/`，完整工作台是 `http://127.0.0.1:5173/?surface=workbench`，文献页面是 `http://127.0.0.1:5173/literature/`。桌面动态 API 地址和目标文献项目由根页面通过同源 WebView 存储传递，不需要独立前端端口。

## 当前边界

- 文献前端已进入正式桌面导航和构建输出；已安装旧版本要等下一个安装包或应用内更新后才能看到；
- MinerU 与模型流水线已有单元级集成回归，但仍需使用真实 API 和真实论文做联网端到端验收；
- DOI 语义去重、候选标签合并/改名和研究论文/综述最终主档尚未完成；
- 笔记 PDF 仍使用浏览器打印窗口，不是无对话框静默导出。

## 验证

```powershell
npm --prefix frontend run test
npm --prefix frontend run build
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

架构与映射见 [ARCHITECTURE.md](ARCHITECTURE.md)。
