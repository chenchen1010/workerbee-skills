---
name: workerbee-connect
description: 连接「工蜂 Worker Bee」小红书选品采集工具的接口。当用户第一次让你操作工蜂、你不知道接口地址或钥匙、请求吃 401/403、换了电脑、或工蜂重启后连不上时使用。
version: 1.0.0
license: MIT
metadata:
  product: 工蜂 Worker Bee
  related_skills: [workerbee-collect, workerbee-selection, workerbee-content-mining, workerbee-feishu-delivery]
---

# 工蜂接入引导

## 这是什么

「工蜂 Worker Bee」是一款装在用户电脑上的小红书选品采集桌面软件。它在本机开了一个 HTTP 接口，
你可以通过这个接口指挥它：建采集任务（真手机操作小红书）、开选品飞轮、筛机会池、导出到飞书。

本 skill 只解决一件事：**拿到地址和钥匙、验证连得上**。连上之后的具体操作看其他 skill。

## 第一步：拿地址和钥匙

工蜂启动时会写一个「发现文件」，地址和钥匙都在里面：

- Windows：`%APPDATA%\工蜂\api.json`
- macOS：`~/Library/Application Support/工蜂/api.json`
- 客户版把上面路径里的 `工蜂` 换成 `工蜂客户版`

```
{"base_url": "http://127.0.0.1:59354", "key": "wf_live_xxxxxxxx", "pid": 1234, "schema": 1}
```

**端口每次启动都会变**。永远从发现文件现读，不要记住上次的端口，也不要写死在代码里。
连不上的第一反应就是重读这个文件。

如果文件不存在，让用户在工蜂里检查：**设置 → 接口开放 → ①本机档**是否打开。
用户也可以在那个页面直接复制一段完整的引导语（含地址+钥匙）粘贴给你。

## 第二步：验证连通

```bash
curl -s -H "X-Api-Key: <钥匙>" "<base_url>/api/state?task_limit=1"
```

返回带 `devices`/`tasks` 字段就通了。

## 第三步：读接口说明书

```bash
curl -s -H "X-Api-Key: <钥匙>" "<base_url>/api/docs"
```

这是工蜂自己生成的完整端点清单，**永远以它为准**——它随软件版本更新，比任何 skill 里写死的
清单都新。本系列 skill 教的是「怎么打」，`/api/docs` 是「有哪些牌」。

## 认证规则

同一把钥匙全站通用，三种带法都认：

| 方式 | 写法 |
|---|---|
| 推荐 | `X-Api-Key: <钥匙>` |
| 也行 | `Authorization: Bearer <钥匙>` |
| 也行 | `X-Workbench-Key: <钥匙>` |

注意：`/api/v1/*` 系列端点**没有本机免鉴权豁免**，调它们永远要带钥匙。

## 常见故障排查

| 症状 | 原因 | 怎么办 |
|---|---|---|
| 连接被拒绝 / 超时 | 工蜂没开，或重启后换了端口 | 重读发现文件；确认工蜂在运行 |
| 401 | 钥匙不对或没带 | 从发现文件重取钥匙；检查请求头拼写 |
| 403 + `LAN_ACCESS_DISABLED` / `PUBLIC_ACCESS_DISABLED` | 你不是从本机访问，对应档位没开 | 让用户在设置里开对应档；或改从本机访问 |
| 403 + `LICENSE_REQUIRED` | 软件未激活 | 让用户先激活 |
| 403 + `UPGRADE_REQUIRED` | 该功能要高级版 | 告知用户需升级 |
| 返回 410 `DEPRECATED_ROUTE` | 用了老路径 | 改用 `/api/v1/xhs/*` |

## 三档开放的安全边界

工蜂接口有三档，越往下越危险，**开关档位属于敏感操作，必须用户明确同意才能调**：

- **①本机档**：只有这台电脑上的程序能连（默认开，最安全，你通常用这档）
- **②局域网档**：同一个 WiFi 下的设备能连
- **③公网档**：全网可访问——**最危险**，务必用户明确同意

查看当前状态：`GET /api/interface/status`

## 安全提醒

- 钥匙等同于密码，**不要写进聊天记录之外的任何地方**，不要提交到代码仓库，不要发给第三方。
- 所有"真占手机 / 耗采集额度 / 对外开放接口"的操作，先把打算做什么讲给用户听、得到确认再发请求。
