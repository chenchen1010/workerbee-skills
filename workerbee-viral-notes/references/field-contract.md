# Excel 与飞书字段契约

## 目录

- [1. 标准阶段产物](#1-标准阶段产物)
- [2. UID 搜索 Excel](#2-uid-搜索-excel)
- [3. 蒲公英元数据](#3-蒲公英元数据)
- [4. 候选与深采完整字段](#4-候选与深采完整字段)
- [5. 飞书类型](#5-飞书类型)
- [6. 匹配与更新](#6-匹配与更新)
- [7. 验收指标](#7-验收指标)

## 1. 标准阶段产物

```text
01_关键词搜索卡片与UID.xlsx
02_蒲公英UID导出/<UID>.xlsx
03_蒲公英元数据汇总.xlsx
04_爆款筛选明细.xlsx
05_爆款候选笔记.xlsx
06_手机深采集结果.xlsx
07_飞书写回核验.xlsx
```

已有项目命名不同可以沿用，但不得缺少同等信息。手机深采结果既要进入 Excel 证据，也必须追加到候选原行并写回飞书。

## 2. UID 搜索 Excel

至少包含工作表：

- `搜索卡片_原始`：每次搜索的原始卡片；
- `UID_去重`：不同 UID 及所有来源词；
- `轮次收敛`：每轮新增、重复和累计 UID；
- `关键词谱系`：关键词来自哪个上一轮信号。

## 3. 蒲公英元数据

每个 UID Excel 与汇总表至少包含：

```text
UID
note_id
标题
发布时间
一级类目
二级类目
笔记类型
曝光数
阅读数
点赞数
互动数
收藏数
粉丝数
地区
图片URL
笔记链接（note_id拼接）
来源Excel
```

## 4. 候选与深采完整字段

当前验证过的 36 字段主表：

```text
UID
note_id
标题
发布时间
一级类目
二级类目
笔记类型
曝光数
阅读数
点赞数
互动数
收藏数
粉丝数
地区
图片URL
笔记链接（note_id拼接）
候选等级
筛选依据
来源Excel
下一步
深采集_标题（手机）
深采集_note_url
深采集_作者
深采集_正文
深采集_点赞
深采集_收藏
深采集_评论
深采集_分享
深采集_发布时间
深采集_封面图
深采集_图片链接
深采集_挂车商品
深采集_采集状态
深采集_设备
深采集_task_id
深采集_错误
```

API 新增字段不得丢失，应在飞书保留为扩展列：

```text
蒲公英笔记类型
笔记标签
视频链接
笔记封面图链接
图片链接
主页链接
采集状态
采集时间
本轮批次
深采集_视频链接
深采集_笔记标签
```

若 Excel 还没有 `深采集_视频链接`、`深采集_笔记标签`，应在下一轮 Excel 模板中追加，而不是从飞书删除。

蒲公英和 App 对笔记类型判断不一致时，保留 `蒲公英笔记类型` 原值；最终 `笔记类型` 以 App 深采及实际媒体字段为准。

## 5. 飞书类型

- 阅读/曝光/互动/粉丝等新建列优先 Number；
- `采集时间`、发布时间等日期列使用 DateTime，不得把格式化日期字符串长期存成 Text；
- 单个笔记链接可用 URL；
- 多图片/长 URL 列使用 Text；
- 标签使用 Multi-select；
- `本轮批次` 使用 Text，值应能稳定标识一次交付；
- `深采集_task_id` 使用 Number；
- 已有同名字段不得假设类型，先读取飞书实际 type 再转换。

## 6. 匹配与更新

优先级：

1. note_id；
2. 已回读保存的 record_id；
3. UID + 唯一标题；
4. 短链重定向得到 note_id。

同 UID 同标题或标题相似时不得自动猜测。无法精确匹配的行进入失败清单，不创建可能重复的记录。

命中已有 note_id/record_id 时：

1. 原位更新深采字段；
2. 把 `采集时间` 更新为本轮实际采集/写回时间；
3. 写入本轮批次；
4. 把 record_id 纳入 `本轮验收` 视图；
5. 报告为 `updated_rows`，不得伪装成新建记录。

## 7. 验收指标

报告：

```text
source_rows
source_fields
feishu_records_before/after
matched_rows
created_rows
updated_rows
unresolved_rows
created_fields
checked_nonempty_cells
cell_mismatches
missing_body
missing_cover
video_records
missing_video
correct_body_tags
tag_mismatches
capture_time_field_type
current_batch_time_matches
acceptance_view_id
acceptance_view_records
feishu_base_url
feishu_table_id
acceptance_view_url
direct_record_urls
```

完成标准：

```text
unresolved_rows = 0
cell_mismatches = 0
missing_cover = 0
missing_video = 0
tag_mismatches = 0
capture_time_field_type = DateTime
current_batch_time_matches = source_rows
acceptance_view_records = created_rows + updated_rows
```

最终回复必须明确：

```text
本轮新增记录数
本轮原位更新数
飞书表链接
本轮验收视图链接
回读差异数
```
