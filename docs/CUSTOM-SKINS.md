# 官方签名皮肤

Workmode 0.7.0 起只导入经过官方 Ed25519 私钥签名的 `.workmode-skin`。旧 `.json`、未签名 ZIP、未知签名者以及内容被修改过的皮肤包全部拒绝；旧版 `workmode-public-custom-skin-v1` localStorage 和 `workmode-public-skins-v3` IndexedDB 不再迁移。

这是一项主动收紧的边界。签名皮肤可以携带完整布局 CSS 和视觉 CSS，因此能够重新排布真实内容槽位并逐项重绘界面；相应地，它不再被视为普通数据文件，而是由 Workmode 官方审核、签名和负责兼容性的视觉扩展。

## 内容、布局与视觉

Workmode 本体维护真实项目、文件、会话、消息、工具结果、上下文、设置和状态。React 在稳定位置暴露 `data-skin-slot`：

- `app-shell`、`app-chrome`、`activity-navigation`；
- `workspace-sidebar`、`project-list`、`file-tree`、`session-list`；
- `chat-workspace`、`chat-header`、`context-meter`、`message-stream`、`message`、`tool-call`、`composer`；
- `workspace-resizer`、`file-viewer`、`status-bar`；
- `settings`、`settings-content`。

皮肤的 `layout.css` 决定这些内容如何排列、占多大空间以及窗口变窄时如何降级；`visual.css` 决定字体、颜色、材质、边框、图标、装饰和动画。皮肤没有 JavaScript 或 HTML 入口，不能创建项目数据、伪造工具结果或获得文件/网络权限。需要新增真实数据展示时，必须先由 Workmode 核心提供新的语义槽位。

## 包格式

```text
example.workmode-skin
├─ manifest.json
├─ signature.json
├─ layout.css
├─ visual.css
├─ LICENSE.txt                 可选
├─ fonts/                      可选，由 manifest 声明
├─ images/                     可选，由 manifest 声明
└─ icons/                      可选，由 manifest 声明
```

`manifest.json` 当前继续使用 `workmode-skin/v3` 作为身份、foundation、回退视觉积木和资源声明。压缩包必须同时包含非空 UTF-8 `layout.css` 与 `visual.css`，单个 CSS 最大 512 KB。图片、图标和 WOFF2 字体仍受路径、条目数、压缩前后体积、magic bytes 和清单引用检查约束。

CSS 可以使用 `workmode-asset://<asset-id>` 引用 manifest 中已声明的本地资源。运行时只把这个占位符替换为当前皮肤的临时 Blob URL，切换或停用时撤销 URL、FontFace 和 `<style>`。

## 签名覆盖

`signature.json` 使用 `workmode-skin-signature/v1`：

```json
{
  "schema": "workmode-skin-signature/v1",
  "keyId": "workmode-official-2026-01",
  "algorithm": "Ed25519",
  "files": [
    { "path": "layout.css", "size": 1234, "sha256": "..." }
  ],
  "signature": "..."
}
```

文件列表按路径排序，覆盖除 `signature.json` 自身以外的全部普通文件。应用依次检查 ZIP 边界、签名清单、每个文件的大小和 SHA-256、内置公钥的 Ed25519 签名，全部通过后才解析 manifest 或 CSS。额外文件、缺少文件、重复路径、大小变化、摘要变化和未知 `keyId` 都会失败。

公钥位于 `frontend/src/officialSkinKeys.ts`。私钥只允许存在于被 Git 忽略的 `.release-secrets/official-skin-ed25519.pem` 或 CI secret；不得进入源码、安装包、日志和 Release。

## 官方签包

首次在受信任发布机初始化独立皮肤密钥：

```powershell
node scripts/official-skin.mjs init
```

签包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build-skin-library.ps1 `
  -SkinId green-phosphor
```

初始化命令会在缺失时创建私钥，并把对应公钥写入应用信任表。私钥必须另做离线备份；丢失后只能发布新公钥和新 `keyId`，不能恢复旧签名身份。

奖励皮肤源码、设计样稿、字体、旧 recipe、本地验签清单和签名包统一位于维护机被 Git 忽略的 `local-reference/reward-skin-library/`，不进入 GitHub、安装包、Release 或 GitHub Actions 构建产物。`build-skin-library.ps1` 默认读取该目录，也支持显式 `-SourceRoot` 与 `-PackageRoot`；公开克隆只包含皮肤协议、运行时、安全测试和签名工具，不需要私有库即可构建。

皮肤可独立于应用升级。保持同一 manifest `id`、递增皮肤 `version` 并重新签名后，用户再次导入会覆盖该 ID 的 manifest、签名收据、CSS 和资源；不需要重新安装 Workmode。只有新增核心语义槽位、修改包协议或信任公钥时才需要发布应用版本。

## 导入与本地状态

设置页支持一次选择多个 `.workmode-skin`，逐个验签后写入 version 4 本地皮肤库。只有验签成功的 manifest、签名收据和资源会持久化；选择器不会列出旧未签名皮肤。

皮肤只保存在当前 WebView 本机，不进入项目文件、会话、JSONL 或模型上下文。覆盖安装和应用更新不会主动删除已经验签的新皮肤库。

## 恢复机制

- 皮肤启动时写入临时 boot guard，CSS 和字体稳定加载三秒后清除；若加载阶段崩溃，下次启动自动停用该皮肤。
- CSS、字体或资源运行时失败会立即停用当前皮肤并恢复基础主题。
- 紧急恢复快捷键为 `Ctrl+Alt+Shift+R`，会清除当前官方皮肤选择并刷新应用；它不删除项目、会话、工作记忆或模型配置。

官方签名代表代码审核和发布责任，不代表 CSS 永远没有视觉 bug。每个签名包仍必须按 [皮肤回归基线](SKIN-REGRESSION.md) 验证设置可达、长文档滚动、消息与工具状态、小窗口降级和紧急恢复。
