---
name: workerbee-collect
description: 用「工蜂 Worker Bee」采集小红书数据——建采集任务、选对任务类型（关键词/商品链接/店铺/号主主页/笔记/博主发现/矩阵号猎手/root搜索）、轮询进度、取结果。当用户要采集小红书商品或笔记数据时使用。
version: 1.0.0
license: MIT
metadata:
  product: 工蜂 Worker Bee
  related_skills: [workerbee-connect, workerbee-selection, workerbee-content-mining, workerbee-feishu-delivery]
---

# 工蜂采集作业

前置：先用 `workerbee-connect` 拿到 `base_url` 和钥匙。下文 `$BASE`/`$KEY` 指代它们。

## 核心心智：任务是异步的，真机在跑

每个采集任务都会**真的占用一台安卓手机**去操作小红书 App，一条商品几十秒到几分钟。
所以流程永远是：**建任务 → 拿 task_id → 轮询到终态 → 取结果**。不要建完就立刻取结果。

**建任务前必须先跟用户说清楚要采什么、大概多少条**，得到确认再发请求（真占手机、耗额度）。

## 第一步：选对任务类型（最关键）

工蜂按输入内容**自动识别**类型，多数情况你只要把关键词或链接丢进去：

| 用户想要 | 输入什么 | 自动识别为 |
|---|---|---|
| 按词搜商品 | 普通文字，如 `天赋测评` | `keyword`（按销量搜） |
| 采某个商品详情 | 含 `/goods-detail/` 的链接，或 `xhslink.com/m/` 短链 | `goods_link` |
| 采整店商品 | 含 `/shop/` 或 `/vendor/` 的链接 | `shop_link` |
| 采某号主的笔记 | 含 `/user/profile/` 的链接 | `user_profile_link` |
| 采某篇笔记内容 | 含 `/explore/` 的链接，或 `xhslink.com/o/` 短链 | `note_link` |

还有三种**必须显式指定** `task_type` 的高级类型，见下方"高级任务类型"。

## 第二步：建任务

**批量建（推荐，一次多个词/链接可混填）**：

```bash
curl -s -X POST "$BASE/api/local/tasks/batch" \
  -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"pool":"行业池名","keywords":["天赋测评","https://www.xiaohongshu.com/explore/xxx"],"limit":20}'
```

返回每个任务的 `task_id`。`pool` 是行业池名（要先存在，见 `workerbee-selection`），
`limit` 是每个词采多少条。

**建高级类型任务**用 `/api/local/tasks/advanced`，见下节。

## 第三步：轮询到终态

```bash
curl -s -H "X-Api-Key: $KEY" "$BASE/api/v1/xhs/tasks/<task_id>"
```

状态含义：

| 状态 | 意思 |
|---|---|
| `pending` | 排队中，等手机空闲 |
| `running` | 手机正在采 |
| `completed` | 采完了（`completion_reason` 说明是采够了还是采光了） |
| `partial` | 部分成功，结果照样能用 |
| `failed` | 失败 |
| `cancelled` | 已取消 |

**轮询节奏**：每 15-30 秒一次即可，别每秒刷。关键词任务通常几分钟，笔记类任务 1-3 分钟一篇，
矩阵号猎手/博主发现可能几十分钟。看 `collected_count` 判断有没有在出货。

看详细进度事件：`GET /api/v1/xhs/tasks/<id>/progress`

## 第四步：取结果

```bash
curl -s -H "X-Api-Key: $KEY" "$BASE/api/task_result?id=<task_id>"
```

- **商品类任务**看 `records`：标题/价格/已售/卖点标签/店铺名/店铺链接/商品ID/图片链接
- **笔记类任务**看 `notes`：标题/作者/UID/赞藏评/分享数/发布时间/正文/正文话题标签/封面与图片链接/
  视频链接；挂车商品在 `notes[].goods_cards`
- **矩阵号猎手**另有 `matched_creators`（命中的矩阵号）、`evidence_notes`（逐条挂车证据）

`ok:true` 只代表查询成功。`partial`/`failed` 的任务照样有结果，别当错误整个扔掉。

## 高级任务类型（必须显式指定）

用 `POST /api/local/tasks/advanced`（一把工蜂钥匙即可，不用另外的钥匙）：

**博主发现**——按关键词扫笔记流，提取作者 UID：
```json
{"task_type":"creator_discovery","keywords":["天赋测评","性格测试"],
 "note_limit_per_keyword":30,"max_scrolls":10}
```
单任务最多 10 个词、每词最多 60 篇。结果在 `notes[].user_id`。

**矩阵号猎手**——顺着某个店铺反查在带货它的账号：
```json
{"task_type":"matrix_creator_discovery","keywords":["泡脚包"],
 "target_seller_id":"<商家ID>","note_limit_per_keyword":30,"max_scrolls":10}
```
目标也可给 `target_shop_url`/`target_goods_id`/`target_goods_url`。
**适用边界**：它靠"笔记挂车"反查，**只在博主普遍挂车的赛道有效**。虚拟品（测评链接、资料包等）
多数靠店铺直销、笔记不挂车，此路命中率极低——那类赛道请改用 `workerbee-content-mining` 的
博主发现路线。0 命中返回 `completed` + `no_matrix_match`，**只说明本轮没发现，不能断言该店没有矩阵号**。

**root 手机关键词搜索**——秒级抓搜索结果（需要用户有 root 设备，没有就跳过）：
```json
{"task_type":"root_keyword_search","keyword":"天赋测评","pages":3,"device_serial":"<序列号>"}
```

## 计费与额度

- 建任务时按目标条数**预扣**额度，**只有真采到货才结算扣费；没出货全额退回**。
- 查余额：`GET /api/v1/xhs/key-summary`，看 `collection_available`。
- 额度不足建任务会返回明确错误码。

## 取消任务

```bash
curl -s -X POST -H "X-Api-Key: $KEY" "$BASE/api/v1/xhs/tasks/<id>/cancel" -d '{}'
```

- 排队中的任务：立即变 `cancelled`
- 正在跑的任务：先返回 `cancelling`，手机跑到下一个检查点才真正停下（通常几十秒），
  最终变 `cancelled` 并退回未使用的额度。**耐心等，别反复点**。
- root 抓包类任务在抓包窗口内（最长约 5 分钟）无法中断，会等窗口结束才生效。

## 常见坑

- **别在任务还在跑的时候取结果**就下结论说"采集失败"，先看状态。
- **一次别建太多任务**：设备数量有限，20 个任务排队要很久。先问用户要多少。
- 同一批任务混填关键词和链接是允许的，工蜂会逐条识别。
- 采集失败会自动换设备重试，不用你手动重建任务。

## 采完之后

结果要给用户看，通常下一步是导出到飞书多维表格——**用 `workerbee-feishu-delivery`，
它有固化好的字段模板，不要自己拼字段调飞书 API**。
