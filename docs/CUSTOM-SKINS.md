# 本地声明式皮肤

Workmode Public 0.6.1 支持从「设置 → 外观与皮肤」导入本地 `.workmode-skin.json`。该格式可描述视觉 token 和由应用维护的 HUD 结构预设，但不是插件系统。

## 安全边界

导入器使用浏览器原生文件选择器读取用户主动选择的单个 `.json` 文件，不获得目录或任意文件读取权限。文件最大 32 KB，导入后只保存经过白名单清洗的对象。HUD 仍由 Workmode 自带的 React 组件渲染，只接收项目名称、路径、模型、生成状态和本地时间等既有只读状态。

格式不接受：

- CSS、JavaScript、HTML、Lua 或其他代码/标记；
- URL、网络资源或远程字体；
- 图片、可执行文件、DLL 或脚本；
- 项目、模型、工具或 API Key 权限；
- schema 未声明的任意字段。

皮肤状态保存在桌面 WebView 的 `localStorage` 键 `workmode-public-custom-skin-v1`，不进入项目、会话、模型上下文或后端配置。覆盖安装和应用内更新不会主动删除它；解析失败时忽略自定义皮肤并保留内置主题。

## v1 格式

```json
{
  "schema": "workmode-skin/v1",
  "id": "neon-ice",
  "name": "Neon Ice",
  "version": "1.0.0",
  "baseTheme": "neon-space-lab",
  "chrome": {
    "type": "hud",
    "title": "NEON ICE",
    "subtitle": "LOCAL RESEARCH HUD",
    "missionLabel": "ACTIVE PROJECT",
    "modelLabel": "MODEL LINK",
    "stateLabel": "CORE STATE",
    "timeLabel": "LOCAL TIME",
    "panelGeometry": "stepped",
    "bubbleGeometry": "mirrored"
  },
  "tokens": {
    "accent": "#66e8ff",
    "background": "#02070c",
    "surface": "#07111a",
    "text": "#e6fbff",
    "panelOpacity": 0.12,
    "lineWidth": 2,
    "radius": 4,
    "glow": 0.45
  }
}
```

字段约束：

| 字段 | 允许值 |
| --- | --- |
| `schema` | 固定为 `workmode-skin/v1` |
| `id` | 1–40 位小写字母、数字和连字符 |
| `name` | 1–48 个字符 |
| `version` | SemVer，例如 `1.0.0` |
| `baseTheme` | 内置主题 ID；受原主题解锁条件约束 |
| `chrome.type` | 当前支持 `hud`；声明 HUD 时 `baseTheme` 必须是 `neon-space-lab` |
| `chrome.title/subtitle` | 顶部 HUD 品牌与副标题，分别最多 24/32 字符 |
| `chrome.*Label` | 任务、模型、状态和时间区标签，最多 20–24 字符 |
| `chrome.panelGeometry` | `stepped` 或 `continuous` |
| `chrome.bubbleGeometry` | `mirrored` 或 `continuous` |
| `accent/background/surface/text` | `#RRGGBB` |
| `panelOpacity` | `0`–`0.8` |
| `lineWidth` | `1`–`4` CSS px |
| `radius` | `0`–`24` CSS px |
| `glow` | `0`–`1` |

皮肤至少需要一个 `tokens` 视觉参数或一个 `chrome` HUD 声明，因此纯 HUD 皮肤也可用。导入新皮肤会替换当前本地皮肤；选择任意内置主题会停用但不卸载本地皮肤，用户可以再次启用或手动卸载。

示例文件位于 [`examples/skins/neon-ice.workmode-skin.json`](../examples/skins/neon-ice.workmode-skin.json)。

## 为什么不支持任意 CSS

CSS 可以隐藏安全按钮、覆盖伪界面或通过 `url()` 发起网络请求，因此不能等同于无害的颜色文件。v1 只把白名单 token 映射到程序维护的语义变量，并用有限枚举选择应用维护的 HUD、主舱和气泡几何；皮肤不能新增按钮、事件、HTML、工具或数据读取。全新的交互组件仍需进入项目源码并经过正常测试、构建和发布。
