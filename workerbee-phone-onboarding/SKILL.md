---
name: workerbee-phone-onboarding
description: 诊断并完成「工蜂 Worker Bee」新安卓手机的首次连接、USB 调试授权、输入组件安装和深度采集自检。当用户新接小米、Redmi、MIUI、HyperOS 或其他 Android 手机，设备显示未授权/已停牌/不可采集，补装组件失败，或出现 INSTALL_FAILED_USER_RESTRICTED、missing_adb_keyboard、nuitka_resource_reader_files 时使用。
---

# 工蜂手机首次连接

只使用已安装的工蜂客户端、客户端自带的 adb/组件和本机 API 完成配置。不要要求客户下载项目源码、安装 Python 依赖或修改数据库。

## 工作流

1. 让用户启动工蜂，用数据线连接手机，保持手机亮屏并解锁。
2. 运行只读检查，不先重启核心或反复安装：

   ```bash
   python scripts/phone_onboarding.py status
   ```

3. 根据 `diagnosis` 处理唯一的前置阻塞。用户完成手机上的授权后，执行：

   ```bash
   python scripts/phone_onboarding.py provision --serial <status 返回的 serial>
   ```

4. 等脚本返回最终结果。只有 `ready=true`、`smoke.state=passed` 且 `collection_capable=true` 才能说新手机已可采集。健康检查、组件安装或界面显示在线都不能代替至少保存 1 条商品链接的深度自检。

## 手机侧分支

- `unauthorized`：让用户在手机弹窗勾选“始终允许这台电脑”并点允许。不要重置 adb key 或删用户配置。
- 没有开启 USB 调试：指导用户进入“设置 → 关于手机”连点版本号，再在开发者选项开启 USB 调试。
- 小米/Redmi/MIUI/HyperOS 出现 `INSTALL_FAILED_USER_RESTRICTED` 或 `adb_keyboard_install_blocked`：停止自动重试。让用户在“设置 → 更多设置 → 开发者选项”开启「USB 调试（安全设置）」和「通过 USB 安装」。某些系统需要插 SIM 卡、登录小米账号或联网确认；这是手机安全门禁，不得用命令绕过。开启后重插数据线，再运行 `provision`。
- `xhs_app=false`：让用户从正式渠道安装并登录小红书；不要随 Skill 分发小红书 APK。
- `nuitka_resource_reader_files`：这是旧安装包的冻结资源推送缺陷，不是手机设置问题。让用户安装包含 PathLike 兼容修复的新版工蜂，不要去改客户电脑上不存在的源码。
- 手机熟睡、锁屏或小红书不在前台：先让用户亮屏解锁，再重试。不要把启动态问题误判为采集逻辑问题。

## 多手机与运行安全

- 同时连多台时必须显式传 `--serial`，不要猜。
- 如果设备正在 `running` 或 `smoking`，等待它结束，不要叠加第二个自检或重启采集核心。
- 不要打印、回传或保存 discovery 文件中的完整钥匙。脚本不会输出钥匙。
- 不要删掉设备健康记录、绕过授权或修改套餐设备上限。
- 失败时保留脚本 JSON 输出中的 `error` 与 `next_steps`，但在对用户解释时翻译为人话。

## 脚本

`scripts/phone_onboarding.py` 使用 Python 标准库读取工蜂 discovery 文件，只连接回环地址，调用 `/api/device-wizard/status`、`/api/device-provision` 和设备详情端点。可用 `--discovery <api.json>` 覆盖自动发现路径。
