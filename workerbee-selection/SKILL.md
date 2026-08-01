---
name: workerbee-selection
description: 用「工蜂 Worker Bee」做小红书选品——多轮自适应选词找爆品、识别脏词死词、建行业池、开选品飞轮、筛机会池、看日销趋势找正在起量的品、历史补筛。当用户要找爆款商品、选品、看销量涨没涨、做行业调研时使用。
version: 1.0.0
license: MIT
metadata:
  product: 工蜂 Worker Bee
  related_skills: [workerbee-connect, workerbee-collect, workerbee-content-mining, workerbee-feishu-delivery]
---

# 工蜂选品打法

前置：`workerbee-connect` 拿地址钥匙，`workerbee-collect` 会建任务取结果。本 skill 教**怎么打**。

## 核心方法：多轮自适应，不是一次采完

新手做法是想 10 个词一次采完交差。正确做法是**打完一轮看战况再定下一轮**：

```
第1轮：8-10 个候选词，每词 20 条  →  看战况
        ↓
      砍死词、识脏词、抄爆品命名
        ↓
第2轮：新词 + 补采强势词，条数按火爆度分配  →  再看
        ↓
第3轮：只深挖已验证的方向
```

**每轮之间必须做判断**，这是选品的价值所在。直接把第一轮结果丢给用户 = 没做选品。

## 每轮看什么

取结果后（`GET /api/task_result?id=`），按词聚合这三个数：

1. **最高已售** —— 这个词有没有天花板
2. **命中热信号的条数** —— `卖点标签` 里有没有 `24小时销量飙升`/`24小时内N人加购`/`N人正在看`。
   这是"当下正在热卖"的实时信号，比历史总销量更值钱
3. **价格带** —— 爆品集中在哪个价位

## 三种要立刻处理的词

**脏词**：搜出来的东西跟你要的不是一回事。
> 实案：搜「职业测评」，前排全是西装正装、面试战袍、鼠标（¥179-1099 实物）——平台按字面
> 匹配了"职业"。真正的测评品得用「天赋测评」「历史人物测试」这类词才捞得准。
>
> 识别方法：看 TOP 商品的标题和价格带，跟预期品类对不上就是脏词。**立刻换词，别浪费额度**。

**死词**：能搜到对的东西，但最高销量很低。
> 实案：「MBTI测试」最高才 634、「恋爱测试」475，而同赛道「历史人物测试」有 2.3 万。
> 说明这个赛道的爆点不在通用概念，而在**新奇具体的角色化玩法**。
>
> 处理：砍掉，别在下一轮浪费条数。

**金词**：多条爆品 + 多个热信号。
> 处理：下一轮加大条数深挖，并且**抄它的命名方式当新词**——爆品标题里的说法就是用户真实搜索词。

## 条数按火爆度分配

不要每个词都给一样的条数：

- 已验证的金词：20-30 条
- 新试探的词：10 条够了，看看有没有货
- 补采的词：看上轮采够没有

## 建行业池

采集任务要挂在行业池下（池是关键词和命中商品的集合）：

```bash
curl -s -X POST "$BASE/api/pools/create" -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" -d '{"name":"池名","description":"说明"}'
```
幂等，已存在不会报错。给已有池加词用 `POST /api/pools/keywords`（只入池，不建采集任务）。

## 选品飞轮（自动多轮循环）

如果用户想让工蜂自己跑多轮，用飞轮——**它会自动采一轮→AI 按命中率繁殖新词→再采**：

```bash
# 先让工蜂 AI 拟第一批词
curl -s -X POST "$BASE/api/campaign/propose" -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" -d '{"pool":"池名"}'

# 开跑（会持续真占手机，务必先跟用户确认规模）
curl -s -X POST "$BASE/api/campaign/start" -H "X-Api-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"pool":"池名","first_keywords":["词1","词2"],"target_hits":50,"max_rounds":5,"round_task_limit":3}'
```

看状态 `GET /api/campaign/status`，叫停 `POST /api/campaign/stop`。
飞轮启动后自主循环，不用你逐轮干预。**开飞轮前必须让用户明确同意规模和上限。**

## 机会池筛选

命中「24小时加购」等热度信号的商品会进机会池：

```bash
# 跨池看商品，可排序可筛选
GET /api/pools/items?pool=&status=all&sort=daily_revenue:desc&page=1&page_size=20

# 人话转筛选条件
POST /api/pools/filter/translate  {"text":"价格大于30按日营收降序"}

# 收藏 / 人工改判
POST /api/pools/item/favorite  {"item_id":"...","favorite":true}
POST /api/pools/item/status    {"item_id":"...","pool":"池名","status":"confirmed"}
```

可排序字段：price/sold/cart/daily_revenue/total_revenue/created_at。

## 日销监控：找「正在起量」的品（不占手机，免费）

一次性销量只能看到"卖了多少"，**日销监控看到的是"正在涨多快"**——后者才是能不能追进去的依据。
工蜂每天自动给机会品记一次销量，攒几天就能出趋势。

**主用法「谁在涨」**：
```bash
GET /api/sales/movers?days=7&limit=20&pool=池名
```
每项带：`increment`（窗口内销量增量）/ `daily_avg`（日均增量）/ `growth_pct`（增幅%）/
`first_sold`→`last_sold` / `points`（样本天数）/ `price_changed`（期间有没有调价）。

**怎么读这些数**：

- **增量大 + 增幅小** = 大盘老品在稳定出货，跟进门槛高
- **增量中 + 增幅大** = 新品正在起飞，**最值得追**
- **`price_changed=true`** = 期间调过价，涨量可能是降价换来的，别只看销量
- **`points` 少** = 样本天数不够，结论要谨慎

**看单品曲线**：
```bash
GET /api/sales/trend?item_id=<商品ID>&days=30
```
`points[]` 每天带 `daily_increment`。**`trend_ready=false` 表示样本不足两天，
这时候不许下"在涨/没涨"的结论**，如实告诉用户数据还不够。

**看监控总览**：`GET /api/sales/status` —— 今天跑没跑、在监控多少品、攒了几天数据。

**手动补跑一轮**：`POST /api/sales/snapshot` `{"limit":0,"concurrency":4}`。
serve 里内置的每日 worker 会自动跑，一般只在"想立刻看今天数据"时才手动调。
它只读商品网页，不占手机、不耗采集额度，可以放心调。

## 历史补筛（不占手机，免费）

库里可能有以前采过但没进池的命中品，可以离线回捞：

```bash
# 先试算，看能捞回多少
POST /api/pools/backfill  {"dry_run":true}
# 确认后真写库
POST /api/pools/backfill  {"dry_run":false}
```

`net_new` 是预计新增数。幂等，重复跑不会重复入池。**这是零成本的，值得先做一次再决定要不要新采。**

## 汇报给用户时

不要只丢一张商品列表。要给出**判断**：

- 哪些词是金词、哪些是脏词死词，为什么
- 爆品的共同特征是什么（价格带/命名方式/卖点信号）
- 下一轮建议打哪里

导出结果用 `workerbee-feishu-delivery`（`template=goods`）。
