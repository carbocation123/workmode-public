# Windows 桌面发行与自动更新

本文面向发行维护者。普通用户只需要从 GitHub Releases 下载安装器，并在应用内检查更新。

## 用户拿到什么

正式 Windows x64 Release 发布一个安装器：

```text
workmode-public-<version>-windows-x86_64-setup.exe
```

安装器包含 React 前端、FastAPI 后端、Python runtime、后端依赖和官方科研协作教程初始模板。目标电脑不需要 Node.js、Python 或 Rust，默认按当前用户安装，不要求管理员权限。

首次启动会显示可跳过的新手向导：模型草稿先做连接探测，成功后才落本机配置；DeepSeek 新用户可从向导打开官方注册、充值和 API Key 页面，并一键填入官方 V4 Pro/Flash 配置；随后用户选择教程或自己的项目，并通过六步界面高亮开始工作。外部链接由 Tauri Opener 在系统浏览器打开，capability 仅允许 DeepSeek 官方平台和文档域名。引导、教程任务和成就状态保存在桌面 WebView 本地存储，不写进用户项目或模型上下文。

皮肤偏好和降低动效开关也保存在 WebView 本地存储。升级或覆盖安装不迁移、上传或写入项目；若本地值损坏或来自未来不兼容版本，前端回退到稳定的实验室主题。Origin Ring 与 Neon Space Lab 的解锁只读取本地教程毕业成就，基础亮色、暗色和高对比皮肤始终可用。Neon Space Lab 随前端源码编译进安装包，只包含项目原创 React/CSS/SVG；参考包中的可执行文件、脚本、字体、图片和配置均不进入仓库或 Release。

0.6.1 起，完整设置页可导入最大 32 KB 的 `.workmode-skin.json`。文件由 WebView 原生文件选择器读取，不新增任意文件系统权限；解析后仅保存白名单视觉 token 到 `workmode-public-custom-skin-v1`。安装器和更新器不主动删除该键，损坏或不兼容状态会被忽略。任意 CSS、JavaScript、URL、图片和权限字段都不是 v1 发行格式的一部分。

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

正式 Release 使用 `.github/workflows/release-windows.yml` 的手动工作流：

```text
Actions → Publish Windows release → Run workflow
```

输入新的 SemVer 版本号后，工作流会：

1. 用 `scripts/sync-version.ps1` 同步 `VERSION`、前端、桌面、Tauri 和 Cargo 版本；
2. 在需要时以 `github-actions[bot]` 提交并推送版本变更；
3. 固定 npm 10.9.4，并用 `npm ci` 安装锁文件指定的 Node 依赖，再安装 Python 和 Rust 依赖；
4. 恢复 pip、Cargo registry/git 和 Tauri target 缓存；
5. 运行后端、前端与 Rust/Tauri 验证；
6. staging 后端、Python runtime、依赖、默认配置和 `tutorial-project/` 初始模板；
7. 构建 Windows NSIS 安装器；
8. 生成 Tauri 更新签名、`latest.json` 和 `SHA256SUMS.txt`；
9. 创建 `v<version>` Release，或安全覆盖同版本 Release 的产物。

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
