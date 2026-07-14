# Windows 桌面发行与自动更新

本文面向发行维护者。普通用户只需要从 GitHub Releases 下载安装器，并在应用内检查更新。

## 用户拿到什么

正式 Windows x64 Release 发布一个安装器：

```text
workmode-public-<version>-windows-x86_64-setup.exe
```

0.7.0 起 GitHub Release 只包含安装器、更新签名、更新清单和校验文件，不再附带 `.workmode-skin`。用户取得维护者手动发放的奖励皮肤后，可在「设置 → 外观与皮肤」中选择一个或多个包导入；皮肤不需要复制进安装目录，也不需要重新安装应用。

安装器包含 React 主工作台与文献智库页面、FastAPI 后端、Python runtime、后端依赖和官方科研协作教程初始模板。两个前端页面由同一个 Vite 构建输出到 `frontend/dist`，Tauri 将整份目录打入应用；文献智库不需要额外端口、Node 进程或第二个安装包。目标电脑不需要 Node.js、Python 或 Rust，默认按当前用户安装，不要求管理员权限。

首次启动会显示可跳过的新手向导：模型草稿先做连接探测，成功后才落本机配置；DeepSeek 新用户可从向导打开官方注册、充值和 API Key 页面，并一键填入官方 V4 Pro/Flash 配置；随后用户选择教程或自己的项目，并通过六步界面高亮开始工作。外部链接由 Tauri Opener 在系统浏览器打开，capability 仅允许 DeepSeek 官方平台和文档域名。引导、教程任务和成就状态保存在桌面 WebView 本地存储，不写进用户项目或模型上下文。

皮肤偏好和降低动效开关也保存在 WebView 本地存储。升级或覆盖安装不迁移、上传或写入项目；若本地值损坏或来自未来不兼容版本，前端回退到稳定的实验室主题。Origin Ring 与 Neon Space Lab 的解锁只读取本地教程毕业成就，基础亮色、暗色和高对比皮肤始终可用。Neon Space Lab 随前端源码编译进安装包，只包含项目原创 React/CSS/SVG；参考包中的可执行文件、脚本、字体、图片和配置均不进入仓库或 Release。

0.7.0 是一次主动断开的皮肤协议升级。WebView 文件选择器只接受 `.workmode-skin`，应用在解析 manifest 和 CSS 之前校验内置 Ed25519 公钥、完整文件集合、大小和 SHA-256；只有官方签名包才写入 `workmode-public-official-skins-v1` 本地库与同名 IndexedDB。旧 `.workmode-skin.json`、未签名包、`workmode-public-custom-skin-v1` 和 `workmode-public-skins-v3` 不迁移。签名包可以包含布局/视觉 CSS 与本地字体图片，因此按受信任的官方界面代码处理；它仍不能携带 JavaScript、HTML 或新增 Tauri 权限。

应用在皮肤加载阶段写入 boot guard，稳定三秒后清除；异常退出后下次启动自动停用该皮肤。运行时资源错误也会回退基础主题。`Ctrl+Alt+Shift+R` 仅清除皮肤选择并刷新应用，不删除用户数据。奖励皮肤维护库位于被 Git 忽略的 `local-reference/reward-skin-library/`；Release 构建脚本完全不读取 `local-reference/` 或 `.release-secrets/official-skin-ed25519.pem`，GitHub Actions 只上传 `release/desktop-<version>/` 根目录中的应用产物。

设置页“快速反馈 Bug”使用安装包内置的公众号二维码，并允许用户复制脱敏诊断模板或通过系统默认邮件客户端写信给 `yantianxue_skye@qq.com`。打开反馈弹窗不会上传数据；Tauri Opener 仅放行 `mailto:*`，邮件发送必须由用户在邮件客户端中确认。模板不读取项目名、路径、会话正文或 API Key。

用户状态位于 `%LOCALAPPDATA%\WorkmodePublic`，不放进安装目录：

```text
config\.env
data\
logs\
```

因此正常覆盖安装、应用内升级和卸载程序文件不会主动删除项目注册、会话、工作记忆或 API 配置。

## 普通用户升级流程

1. 打开「设置 → 桌面应用」；
2. 点击检查更新；
3. 有新版本时点击下载并安装；
4. 应用验证签名、显示下载进度、停止本地后端、启动安装器并退出；
5. 安装完成后重新打开 Workmode Public。

更新安装前必须终止并等待后端进程树，否则 Windows 可能因 Python 扩展模块仍被加载而拒绝覆盖 `.pyd` 文件。若安装器在应用退出前拒绝启动，桌面壳会尝试恢复原后端。

直接运行一个更新版本的安装器也会覆盖同一应用安装。不要同时运行两个安装器；遇到文件占用时，先退出 Workmode Public 和旧安装器，再重试。

## GitHub Actions 正式发行

正式 Release 使用 `.github/workflows/release-windows.yml`。推荐在版本文件已经同步并通过本地测试后推送 SemVer 标签，GitHub 会自动云构建：

```powershell
git tag v0.7.1
git push origin v0.7.1
```

也保留网页手动入口：

```text
Actions → Publish Windows release → Run workflow
```

标签触发时，标签版本必须与提交中的全部版本文件一致，否则立即失败且不会重写标签；网页手动触发时可输入新的 SemVer 版本号并由工作流同步版本。随后工作流会：

1. 用 `scripts/sync-version.ps1` 同步 `VERSION`、前端、桌面、Tauri 和 Cargo 版本；
2. 在需要时以 `github-actions[bot]` 提交并推送版本变更；
3. 固定 npm 10.9.4，并用 `npm ci` 安装锁文件指定的 Node 依赖，再安装 Python 和 Rust 依赖；
4. 恢复 pip、Cargo registry/git 和 Tauri target 缓存；
5. 运行后端、前端与 Rust/Tauri 验证；
6. staging 后端、Python runtime、依赖、默认配置和 `tutorial-project/` 初始模板；
7. 构建 Windows NSIS 安装器；
8. 生成 Tauri 更新签名、`latest.json` 和 `SHA256SUMS.txt`；
9. 创建 `v<version>` Release，或安全覆盖同版本 Release 的产物。

发行工作流固定使用 npm 10.9.4。提交版本锁文件前，应使用相同版本至少执行一次干净安装，避免较新 npm 生成的可选 peer 依赖记录无法被云端 `npm ci` 接受：

```powershell
npx --yes npm@10.9.4 ci --prefix frontend
npx --yes npm@10.9.4 ci --prefix desktop
```

0.8.2 的前端锁文件已用 npm 10.9.4 重新生成并完成两端 `npm ci` 验证；同时修复 GitHub Windows Runner 暴露的临时目录长路径/8.3 短路径别名问题。这些发行修复不改变用户数据格式。

应用内更新端点固定为：

```text
https://github.com/carbocation123/workmode-public/releases/latest/download/latest.json
```

`latest.json` 中 `platforms.windows-x86_64.url` 必须指向同一 Release 中的确切安装器文件，且必须附带非空签名。

## GitHub Secrets

仓库 Actions 需要：

- `WORKMODE_UPDATER_PRIVATE_KEY`：完整 updater 私钥；
- `WORKMODE_UPDATER_PASSWORD`：私钥密码。

私钥不能写入 issue、commit、workflow 日志或聊天。开发机上的等价文件为：

```text
.release-secrets/workmode-public-updater.key
.release-secrets/updater-password.txt
```

`.release-secrets/` 必须保持 Git ignored。公钥可以编译进 `desktop/src-tauri/tauri.conf.json`。

Tauri 更新签名验证下载内容来自发布者，但不提供 Windows 发布者身份。若没有 Authenticode，SmartScreen 仍可能提示未知发布者。

## 本地构建

本地 Windows 构建机需要：

- Node.js 22 与 npm 10.9.4；
- Python 3.14 和准备好的 `backend/.venv`；
- Rust stable 与 `x86_64-pc-windows-msvc` target；
- Visual Studio C++ Build Tools；
- WebView2 构建支持；
- 本地 updater 私钥和密码。

执行：

```powershell
.\scripts\build-desktop.ps1
```

脚本验证版本一致性，运行测试，构建前端和 Tauri/NSIS，签名更新产物，并检查发行目录中没有私钥。只有同一 source revision 已经通过完整检查时才使用 `-SkipTests`。

输出位于：

```text
release/desktop-<version>/
  workmode-public-<version>-windows-x86_64-setup.exe
  workmode-public-<version>-windows-x86_64-setup.exe.sig
  latest.json
  SHA256SUMS.txt
```

`release/` 是构建产物目录，不提交到 Git。

## 图标维护

规范源图是：

```text
desktop/src-tauri/icons/icon-source.png
```

替换源图后运行：

```powershell
npm --prefix desktop run tauri -- icon src-tauri/icons/icon-source.png
```

当前只发布 Windows NSIS，因此仓库只保留 `32x32.png`、`128x128.png`、`128x128@2x.png` 和 `icon.ico` 等 Tauri 配置实际引用的 Windows 资源。生成器同时产生的 Android、iOS、macOS 和 Store 资源被 `.gitignore` 排除；它们应在真正增加相应平台目标时再纳入版本控制。

Windows Shell 可能缓存旧桌面快捷方式图标。安装新版本后若图标未立即变化，重新创建快捷方式或重启 Explorer；这与安装器内嵌图标是否正确是两个问题。

## 0.1.x 便携版数据迁移

早期便携发行实现已经退役，但桌面设置页继续提供非破坏性数据导入：

- 来源必须包含 `data/work`，也可以直接选择 `data` 目录；
- 只复制 `data/` 和可选的 `config/.env`；
- 目标桌面数据非空时拒绝迁移，避免覆盖；
- 旧目录不会被修改，确认桌面版数据完整后由用户自行决定是否删除。

这是一条兼容迁移路径，不是当前发行或更新方式。

## 发行检查清单

- `main` 工作区干净且已推送；
- 所有版本源一致；
- 后端、前端和 Rust/Tauri 测试通过；
- staging 中存在教程标识、`WORKMODE.md` 和真实教学 PDF，教程进度保持初始态；
- 首次向导可跳过、可重新播放，模型测试失败不会写入配置；教程任务与成就只由真实操作事件推进；
- 安装器文件名、`latest.json` URL 和签名一致；
- Release 不是 draft/prerelease，且被标记为 latest；
- 发行产物和 Git 历史中没有 `.env`、`sk-`、私钥或密码；
- 在无 Node/Python/Rust 的干净 Windows 用户环境做安装、首启、更新和卸载保留数据验证。
