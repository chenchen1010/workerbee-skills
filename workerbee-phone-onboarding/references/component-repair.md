# 手机组件补装兜底

仅在工蜂应用内的“补装组件/重新自检”无法解决时使用。资源已经随 Skill 固定分发，不让用户自行搜索同名 APK/JAR。

## 顺序

1. 保持手机亮屏解锁，确认 USB 调试已授权。
2. 先运行 `phone_onboarding.py status`，确认设备没有正在采集或自检。
3. 运行 `component_fallback.py assets`，必须看到两个资源 `ok=true`。
4. ADB Keyboard 缺失时，先让用户在手机上开启厂商要求的 USB 安装权限，再执行 `install-keyboard --yes`。
5. 仅当错误明确包含 `nuitka_resource_reader_files`、`u2.jar` 缺失或旧安装包无法推送资源时，执行 `push-u2 --yes`。
6. 回到工蜂应用点击“重新自检”，以真实深度自检结果收尾。

## 用户需要点击的设置

- 通用 Android：设置 → 关于手机 → 连点版本号 → 开发者选项 → USB 调试。
- 小米/Redmi/MIUI/HyperOS：开发者选项 → 开启「USB 调试（安全设置）」和「通过 USB 安装」。系统要求时完成小米账号、SIM 卡或联网确认。
- 输入法安装成功但系统仍未启用：打开“设置 → 语言与输入法/管理键盘”，启用 ADB Keyboard。不要把它长期设为日常输入法；工蜂采集时会临时切换。

## 命令

在 Skill 目录执行；同时连接多台手机时必须传真实 serial。

```bash
python scripts/component_fallback.py assets
python scripts/component_fallback.py status --serial <serial>
python scripts/component_fallback.py open-settings --serial <serial> --page developer --yes
python scripts/component_fallback.py install-keyboard --serial <serial> --yes
python scripts/component_fallback.py push-u2 --serial <serial> --yes
```

可用 `--adb <path>` 指定工蜂安装目录里的 adb。脚本会优先自动寻找系统 adb、Mac 工蜂应用和 Windows 默认安装目录中的 adb。

## 安全边界

- `install-keyboard` 只安装固定摘要的 ADB Keyboard，并启用其包和输入法服务；不会切换用户默认输入法。
- `push-u2` 只覆盖 `/data/local/tmp/u2.jar`，不会启动服务、修改系统分区或绕过手机安全开关。
- 任何安装或推送前都要取得用户确认，脚本以 `--yes` 表示本次确认。
- 手机正在采集、自检或交付时不要补装组件。
- ADB Keyboard 来自 GPL-2.0 项目，u2.jar 来自 MIT 项目；来源、提交、许可证与摘要见 `assets/manifest.json`。
