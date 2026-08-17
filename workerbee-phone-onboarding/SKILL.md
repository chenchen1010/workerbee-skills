---
name: workerbee-phone-onboarding
description: 诊断并完成「工蜂 Worker Bee」新安卓手机的首次连接、USB 调试授权、输入组件安装、u2 资源补推和深度采集自检。当用户在桌面应用内点击补装/重试仍无法连接，小米、Redmi、MIUI、HyperOS 或其他 Android 手机显示未授权/已停牌/不可采集，或出现 INSTALL_FAILED_USER_RESTRICTED、missing_adb_keyboard、nuitka_resource_reader_files、u2.jar 缺失时使用。
---

# 工蜂手机首次连接

优先使用已安装工蜂的连接向导。应用内处理不了时，再使用本 Skill 固定分发且带摘要校验的 ADB Keyboard 与 u2.jar；不要让客户搜索来历不明的同名文件、下载项目源码或修改数据库。

## 工作流

1. 让用户启动工蜂，用数据线连接手机，保持手机亮屏并解锁。
2. 运行只读检查，不先重启核心或反复安装：

   ```bash
   python scripts/phone_onboarding.py status
   ```

3. 根据 `diagnosis` 处理唯一的前置阻塞。先引导用户在工蜂中点击“补装组件/重新自检”。用户完成手机上的授权后，执行：

   ```bash
   python scripts/phone_onboarding.py provision --serial <status 返回的 serial>
   ```

4. 等脚本返回最终结果。只有 `ready=true`、`smoke.state=passed` 且 `collection_capable=true` 才能说新手机已可采集。健康检查、组件安装或界面显示在线都不能代替至少保存 1 条商品链接的深度自检。

5. 如果应用内仍失败，读取 [`references/component-repair.md`](references/component-repair.md)，按“资源校验 → 单项补装 → 回应用重新自检”的顺序处理。不要一次执行所有修复：

   ```bash
   python scripts/component_fallback.py assets
   python scripts/component_fallback.py status --serial <serial>
   ```

   - `missing_adb_keyboard`：先让用户开启手机允许 USB 安装的开关，再在用户同意后运行 `install-keyboard --yes`。
   - `nuitka_resource_reader_files` 或明确缺少 `/data/local/tmp/u2.jar`：在用户同意后运行 `push-u2 --yes`。
   - 只需要带用户找到设置时，运行 `open-settings --page developer --yes` 或 `--page keyboard --yes`，由用户亲自点击安全开关。

需要查看完整图文步骤时，打开[《工蜂采集工具 · 使用指南》](https://gcn6bvkburhk.feishu.cn/docx/RhhTdw5B3oe7i8xWMYKcEIQInre)。

## 手机侧分支

- `unauthorized`：让用户在手机弹窗勾选“始终允许这台电脑”并点允许。不要重置 adb key 或删用户配置。
- 没有开启 USB 调试：指导用户进入“设置 → 关于手机”连点版本号，再在开发者选项开启 USB 调试。
- 小米/Redmi/MIUI/HyperOS 出现 `INSTALL_FAILED_USER_RESTRICTED` 或 `adb_keyboard_install_blocked`：停止自动重试。可以替用户打开开发者选项页面，但必须让用户亲自开启「USB 调试（安全设置）」和「通过 USB 安装」。某些系统需要插 SIM 卡、登录小米账号或联网确认；这是手机安全门禁，不得用命令绕过。开启后重插数据线，再运行 `provision`。
- `xhs_app=false`：让用户从正式渠道安装并登录小红书；不要随 Skill 分发小红书 APK。
- `nuitka_resource_reader_files`：这是旧安装包的冻结资源推送缺陷，不是手机设置问题。首选升级新版工蜂；用户暂时不能升级时，才用 Skill 内固定的 u2.jar 执行 `push-u2 --yes`，然后回应用重新自检。
- 手机熟睡、锁屏或小红书不在前台：先让用户亮屏解锁，再重试。不要把启动态问题误判为采集逻辑问题。

## 多手机与运行安全

- 同时连多台时必须显式传 `--serial`，不要猜。
- 如果设备正在 `running` 或 `smoking`，等待它结束，不要叠加第二个自检或重启采集核心。
- 不要打印、回传或保存 discovery 文件中的完整钥匙。脚本不会输出钥匙。
- 安装 APK、推送 jar 或打开手机设置前，先说明动作并取得用户同意；脚本要求显式 `--yes`。
- 不要删掉设备健康记录、绕过授权或修改套餐设备上限。
- 失败时保留脚本 JSON 输出中的 `error` 与 `next_steps`，但在对用户解释时翻译为人话。

## 不是连接故障的拒绝码

- `license_required`：工蜂尚未激活；先在应用内完成激活，不要反复插拔手机。
- `device_limit_exceeded`：当前套餐的设备名额已满；按应用提供的流程移除不再使用的离线设备或升级套餐，不要修改数据库绕过限制。
- `MODULE_NOT_IN_PLAN`：手机可能已经连接正常，但当前套餐不包含用户要运行的采集模块；不要把它误判为 USB、ADB 或组件安装失败。

## 脚本

- `scripts/phone_onboarding.py`：读取工蜂本机接口，完成状态诊断、应用内补装和深度自检。可用 `--discovery <api.json>` 覆盖自动发现路径。
- `scripts/component_fallback.py`：校验 Skill 内组件、寻找安装包自带 adb，并按用户确认单独安装 ADB Keyboard、推送 u2.jar 或打开设置页。
- `assets/manifest.json`：记录两份第三方资源的官方来源、固定版本/提交、SHA-256 与许可证；二进制旁保留完整许可证文本。
