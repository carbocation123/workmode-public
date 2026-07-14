# 开发环境与仓库维护

## 前置环境

仅运行后端/浏览器开发版需要：

- Windows PowerShell；
- Python 3.11+；
- Node.js 20+。

构建正式桌面安装器还需要 Rust、MSVC Build Tools、WebView2 构建支持和 updater 签名材料，详见 [DESKTOP-DISTRIBUTION.md](DESKTOP-DISTRIBUTION.md)。

## 源码一键启动

在仓库根目录双击：

```text
start-workmode-public.cmd
```

启动器会按需创建 `.env`、`backend/.venv`，安装依赖，构建前端，启动 `127.0.0.1:8765` 的 FastAPI 并打开浏览器。它是开发入口，不是给普通用户分发的安装方式。

健康检查同时校验文献项目契约版本。若 8765 已被旧 Workmode 后端占用，启动器会明确报错，不会把旧服务的 HTTP 200 误判为当前源码启动成功。

启动器在复用 `backend/.venv` 前会执行 Python 3.11+ 可用性检查。若虚拟环境文件仍在、但其底层系统 Python 已被移动或卸载，启动器会先核验待删除目录确实是当前仓库的 `backend/.venv`，再自动重建。依赖安装命令的标准输出会直接写到终端，不会成为 `Ensure-Backend` 的返回值；Windows 进程环境中的 `Path`/`PATH` 也会在调用 `Start-Process` 前规范为单一键。

常用参数：

```powershell
.\start-workmode-public.cmd -NoInstall
.\start-workmode-public.cmd -RebuildFrontend
.\start-workmode-public.cmd -NoBrowser
```

停止源码后端：

```text
stop-workmode-public.cmd
```

开发日志位于 ignored 的 `logs/`。`.run/` 只保存 PID、临时发行配置、可重建 smoke 目录和项目自带的开发工具，不保存设计稿、论文或教程历史。

## 手动开发

准备配置：

```powershell
Copy-Item .env.example .env
```

后端：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Push-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765
Pop-Location
```

前端：

```powershell
npm ci --prefix frontend
npm --prefix frontend run dev
```

正式 CI 固定 npm 10.9.4。修改前端依赖后必须用同版本更新并验证 lockfile，不能只依赖已有 `node_modules`：

```powershell
Push-Location frontend
npx --yes npm@10.9.4 install --package-lock-only --ignore-scripts --no-audit --no-fund
npx --yes npm@10.9.4 ci --ignore-scripts --no-audit --no-fund
Pop-Location
```

打开 `http://127.0.0.1:5173` 进入应用级功能大厅，选择「科研工作台」或「文献智库」。需要直接调试时，`http://127.0.0.1:5173/?surface=workbench` 是完整工作台，`http://127.0.0.1:5173/literature/` 是文献智库。三个界面属于同一个 Vite 多页面工程、共享同一后端、浏览器存储与外观基础；不再启动独立的 5176 前端。Vite 开发态会自动将十项成就写为已解锁，用于检查全部内置主题和奖励皮肤入口；通过 `tauri dev` 启动桌面源码时同样生效。一键源码启动器会在自身的前端构建中注入同一维护标记，并用 `dist/.source-achievements` 区分普通生产构建；GitHub Release 与正式安装包不设置该标记。桌面开发使用：

```powershell
npm ci --prefix desktop
npm --prefix desktop run dev
```

## MinerU 与 PDF 直接阅读

MinerU 是可选的增强解析，不是文献对话的硬依赖。设置页「MinerU 文献解析」可保存 Token、`pipeline`/`vlm`、文献语言和 60–1800 秒超时；也可直接在 `.env` 设置：

```text
WORKMODE_MINERU_API_KEY=
WORKMODE_MINERU_MODEL_VERSION=pipeline
WORKMODE_MINERU_LANGUAGE=en
WORKMODE_MINERU_TIMEOUT_SECONDS=180
```

配置后会明显提高多栏正文、表格、公式和版面顺序的识别准确性。没有 MinerU `full.md` 时，`literature_read(part="full_text")` 使用 `pypdf` 读取原 PDF 文本层；扫描件或纯图片 PDF 没有文本层，会返回需要 MinerU/OCR 的明确错误。回归测试既覆盖工具层的降级接线，也用真实生成的最小 PDF 验证文本层抽取与无文本层错误，不能只 mock 解析器。

## 皮肤开发

内置普通皮肤在 `frontend/src/theme.ts` 注册稳定 ID，并在 `frontend/src/styles.css` 通过 `data-theme` 作用域覆盖语义化 token；需要顶部结构或其他额外外壳时，再通过 `frontend/src/SkinChrome.tsx` 注册只读运行状态组件。业务数据和交互组件不能在皮肤中复制一份。

0.7.0 起用户入口只接受官方 Ed25519 签名的 `.workmode-skin`。公开仓库只维护皮肤协议、导入器、运行时、安全回退和签名工具，不存放奖励皮肤源码或样稿。维护机的私有库位于被 Git 忽略的 `local-reference/reward-skin-library/`；每套源码至少包含 `manifest.json`、`layout.css` 和 `visual.css`，字体、图片和图标必须附带许可证。`layout.css` 只能围绕应用维护的 `data-skin-slot` 排列真实内容，`visual.css` 负责外观。不得加入 JavaScript、HTML、远程资源、伪造业务内容或权限声明。

协议、信任表、本地库、包解析、IndexedDB 和运行时分别位于 `skinProtocol.ts`、`officialSkinKeys.ts`、`skinLibrary.ts`、`skinPackage.ts`、`skinAssetStore.ts` 与 `skinAssetRuntime.ts`。修改导入或执行边界时，先更新测试中程序化构造的最小包、未知签名、篡改、路径越界、CSS 注入清理、boot guard 和紧急恢复测试，再同步 [CUSTOM-SKINS.md](CUSTOM-SKINS.md)。旧声明式 JSON recipe 已移出公开仓库，不是导入或分发入口。

签包只在受信任维护机执行：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-skin-library.ps1`。脚本默认读取 `local-reference/reward-skin-library/sources/` 并输出到同级 `packages/`，也可以显式指定 `-SourceRoot` 与 `-PackageRoot`。脚本会净化每套源目录，只复制协议文件、manifest 声明素材和许可证。私钥只能位于被 Git 忽略的 `.release-secrets/official-skin-ed25519.pem`；公钥可进入源码。每次签包后必须运行本地真实包验签测试。桌面发行脚本与 GitHub Actions 不读取或上传私有皮肤库。

静态视觉探索与奖励皮肤回归样稿统一放在私有库的 `design-lab/`，不是可导入皮肤。第三方皮肤解包、游戏截图、真实论文和许可证未确认素材同样只放在 ignored 的 `local-reference/`；公开构建、测试和运行时代码不得依赖这些文件。奖励皮肤专属测试可在本地库存在时运行，在公开克隆中应明确跳过。

## 验证命令

后端：

```powershell
Push-Location backend
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m compileall -q app tests
Pop-Location
```

前端：

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

桌面：

```powershell
cargo test --manifest-path desktop/src-tauri/Cargo.toml --release
powershell -ExecutionPolicy Bypass -File scripts/build-desktop.ps1 -ValidateOnly
```

根据改动范围运行相关检查；影响跨层行为、发行或用户数据时运行完整组合。

## 文档纪律

每次代码、工具、配置、打包或 UI 行为变更必须同时更新：

- 根目录 `README.md` 中的用户可见能力或使用方法；
- `docs/ARCHITECTURE.md` 中的实现和数据流；
- 与发行相关时更新 `docs/DESKTOP-DISTRIBUTION.md`；
- 改变已交付基线或未来优先级时更新 `docs/PRODUCT-ROADMAP.md`。

文档只描述已经实现并验证的行为。提交前用 `git diff --check` 和全文检索排查旧版本号、退役入口及失效链接。

## 仓库卫生

需要提交：源码、测试、锁文件、Tauri 能力 schema、规范图标源和当前 Windows 构建实际引用的图标。

不提交：

- `.env`、API Key、updater 私钥和密码；
- `node_modules/`、Python virtualenv、Cargo `target/`；
- `frontend/dist/`、`release/`、运行日志、PID 和 smoke 安装目录；
- `desktop/src-tauri/resources/` 中构建时 staging 的 runtime；
- 当前未构建的 Android、iOS、macOS 和 Store 图标。

本地目录职责：

- `.run/`：随时可重建的运行态、烟测副本、临时发行配置和项目自带开发工具；
- `local-reference/`：Git 忽略的本地档案，包含奖励皮肤维护库、静态样稿、第三方参考、真实文献和旧实验记录，不属于可随手删除的缓存；
- `local-reference/reward-skin-library/`：奖励皮肤源码、设计稿、旧 recipe、本地验签清单和手动发放包；该目录不进入 GitHub。

删除文件前先确认没有代码、配置、测试、文档或发行流程引用。用户项目、session、JSONL、工作记忆和迁移备份不属于可清理构建产物。

## 分支与发布

普通变更先提交到 `main` 并推送。正式版本不要手工修改一部分版本号；使用 GitHub Actions 的 `Publish Windows release`，由 `scripts/sync-version.ps1` 同步所有版本源并由工作流生成 Release。
