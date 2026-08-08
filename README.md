# 工蜂 Worker Bee · AI 技能包（Skills）

给 Claude Code / Codex / Workbuddy 等 AI 助手用的技能包。装上之后，你可以直接用大白话
指挥 AI 操作「工蜂 Worker Bee」小红书选品采集工具。

## 六个技能

| 技能 | 什么时候自动触发 | 门槛 |
|---|---|---|
| `workerbee-connect` | 第一次连工蜂、连不上、换电脑、报 401 | — |
| `workerbee-collect` | 要采集小红书商品或笔记数据 | — |
| `workerbee-selection` | 找爆款、选品、行业调研、看销量涨没涨 | — |
| `workerbee-content-mining` | 研究博主笔记打法、找带货账号、找未变现机会 | — |
| `workerbee-feishu-delivery` | 导出结果到飞书多维表格 | 需配飞书应用凭证 |
| `workerbee-viral-notes` | 按**阅读数**找行业爆款笔记 | ⚠️ 需**小红书蓝V**资质 |

技能之间会互相调用，你不用记它们的名字——正常提需求就行，AI 会自己判断该读哪个。

**关于蓝V那个**：小红书不公开笔记阅读数，只有蒲公英后台（需企业认证蓝V）看得到。
没有蓝V也能做爆款研究——AI 会自动改用「赞+藏+评」的互动热度来排序，效果对多数选题够用。
技能会在开工前先问你有没有资质，不会让你白跑一趟。

## 怎么安装

### Claude Code

把本仓库里 `workerbee-` 开头的六个文件夹复制到 `~/.claude/skills/`（Windows 是
`C:\Users\<你的用户名>\.claude\skills\`），重开一个会话即可。

### Codex

复制到 `~/.codex/skills/`（Windows：`C:\Users\<你的用户名>\.codex\skills\`）。

### Workbuddy

在 Skills Hub 里搜索并添加。

### 让 AI 自己装

把这段话发给你的 AI 助手：

> 请从 https://github.com/chenchen1010/workerbee-skills 下载 workerbee- 开头的全部技能文件夹，
> 复制到我的 AI 技能目录（Claude Code 是 ~/.claude/skills/，Codex 是 ~/.codex/skills/），
> 然后读一遍 workerbee-connect 技能，帮我连上工蜂。

## 装好之后怎么用

先确保工蜂桌面软件在运行，并且**设置 → 接口开放 → ①本机档**是打开的。

然后直接跟 AI 说人话就行：

- 「帮我看看工蜂现在什么状态，有几台手机在线」
- 「采集『天赋测评』这个词的商品，20 条」
- 「帮我找这个品类卖得最好的品，多跑几轮」
- 「看看这个品类的博主都是怎么发笔记的」
- 「找找有哪些笔记评论区很火但还没做成商品的」
- 「找这个行业阅读数最高的爆款笔记」（会先问你有没有蓝V）
- 「把结果导出到飞书表格」

## 安全说明

- 技能只会调用工蜂在你本机开的接口，**数据不出你的电脑**（除非你让它导出到飞书）。
- 采集会真的占用你连接的安卓手机去操作小红书，AI 会在动手前先跟你确认。
- 你的接口钥匙等同密码，别发给第三方。

## 版本

v1.0.0 · 2026-07-31
