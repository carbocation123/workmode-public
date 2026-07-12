# 酒保行动·像素夜班

当前版本 3.2.1，使用 Workmode 0.7.0 的完整签名皮肤结构。聊天头只保留整条上下文仪表带，项目说明由最顶层状态栏承载；上下文容量、token 数、历史条数和分段进度条按信息组排列。消息框保持完整矩形，工具卡左侧显示由真实工具名映射得到的 `READ / WRITE / PY / WEB / FETCH / MEM / PLAN` 等类型标签，运行状态显示在右侧。项目、设置、文件夹、文件类型、会话以及打开、刷新、移除、重命名按钮使用皮肤自带的 CSS 像素画标识，不再显示系统 Emoji 或通用菱形；文件与会话图标占用独立 24px 槽位，刷新和移除按钮分别使用相向循环箭头与像素废纸篓。

目录中的像素字体为 Fusion Pixel WOFF2，许可证见 `LICENSE.txt`。运行当前目录的 `build-package.ps1`，或在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-skin-library.ps1 -SkinId pixel-night-shift
```

输出位于 `skin-library/packages/pixel-night-shift.workmode-skin`。该包只用于本地测试和手动奖励发放，不进入 GitHub Release；皮肤不会获得文件、工具、网络、模型或系统权限。
