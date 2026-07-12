# Workmode 本地皮肤库

这个目录集中维护 Workmode 的全部奖励皮肤，不再区分“公开皮肤”和“私人皮肤”。

```text
skin-library/
  sources/   可审查、可继续修改的皮肤源文件
  packages/  使用本机官方私钥生成的 .workmode-skin（Git 忽略）
```

`sources/` 当前包含七套皮肤：紫晶星象塔、奶油泡芙、霜核机能台、绿磷终端、午夜控制台、Neon Ice 和酒保行动·像素夜班。皮肤源文件至少包含 `manifest.json`、`layout.css` 与 `visual.css`；本地字体或图片必须在 manifest 的 `assets` 中声明并附带相应许可证。

签名包只用于本地测试和手动奖励发放，不进入 GitHub Release，也不会被桌面安装包或 GitHub Actions 自动收集。生成全部包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-skin-library.ps1
```

只生成一套：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-skin-library.ps1 -SkinId pixel-night-shift
```

脚本只会把协议要求的三个文件、manifest 声明的本地素材和可选 `LICENSE.txt` 放进临时净化目录，再调用 `scripts/official-skin.mjs` 签名。私钥固定留在被 Git 忽略的 `.release-secrets/official-skin-ed25519.pem`。

签完后从 `frontend/` 运行以下本地验签；它会逐个用应用内置生产公钥检查七个包，不属于 GitHub Actions：

```powershell
npx vitest run --root .. skin-library\verify.local.test.ts
```
