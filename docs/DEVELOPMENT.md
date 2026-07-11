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

开发日志和 PID 位于 ignored 的 `logs/` 与 `.run/`。

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

打开 `http://127.0.0.1:5173`。桌面开发使用：

```powershell
npm ci --prefix desktop
npm --prefix desktop run dev
```

## 皮肤开发

内置普通皮肤在 `frontend/src/theme.ts` 注册稳定 ID，并在 `frontend/src/styles.css` 通过 `data-theme` 作用域覆盖语义化 token；需要顶部结构或其他额外外壳时，再通过 `frontend/src/SkinChrome.tsx` 注册只读运行状态组件。业务数据和交互组件不能在皮肤中复制一份。

无需重新打包的本地皮肤使用 `workmode-skin/v1` 或向后兼容的 `workmode-skin/v2` JSON。HUD 可从 `examples/skins/neon-ice.workmode-skin.json` 开始，材质皮肤可从 `examples/skins/cream-puff.workmode-skin.json` 开始，在完整设置页直接导入验证。解析器位于 `frontend/src/customSkin.ts`；结构皮肤由 `SkinChrome.tsx` 选择受维护的 React 外壳，材质皮肤由 `styles.css` 中作用域明确的预设消费解析器生成的有限变量。修改 schema 时必须同步更新版本白名单、旧版兼容测试、越界/注入测试和 [CUSTOM-SKINS.md](CUSTOM-SKINS.md)；不要加入原始 CSS、JavaScript、HTML、URL、外部素材或权限字段。

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

删除文件前先确认没有代码、配置、测试、文档或发行流程引用。用户项目、session、JSONL、工作记忆和迁移备份不属于可清理构建产物。

## 分支与发布

普通变更先提交到 `main` 并推送。正式版本不要手工修改一部分版本号；使用 GitHub Actions 的 `Publish Windows release`，由 `scripts/sync-version.ps1` 同步所有版本源并由工作流生成 Release。
