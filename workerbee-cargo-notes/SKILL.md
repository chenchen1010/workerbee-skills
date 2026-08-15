---
name: workerbee-cargo-notes
description: "小红书带货笔记挖掘：采集博主主页笔记(按点赞/时间/挂车商品筛选)→ 无水印图+视频 → 飞书多维表格。Route-B抓包拿全年列表 + 深链直开逐篇补短链/视频。当用户要盘某博主的带货/挂车笔记、按商品分类笔记、要无水印素材交付飞书表时使用。⚠️ 进阶：需 root 安卓手机 + 工蜂项目源码环境。"
---

# /小红书带货笔记挖掘

把一个小红书博主近一年(或指定区间)的笔记,按「点赞数 / 发布时间 / 是否挂某商品」筛选,
连同**无水印图片 + 视频 + 可点短链 + 全部互动数据**写进飞书多维表格并转移所有人。

**首次跑通:2026-08-12。这条路是踩了大量坑之后固化下来的成功路径。先读文末「踩坑记录」——
其中"残留代理"一个坑就制造了半天的假象,别重蹈。**

## 何时用

- 要盘一个博主的爆款笔记(高赞 + 挂某商品)
- 要笔记的完整字段(无水印图、视频、话题、赞藏评分享、短链)
- 有一台 **root 安卓手机**(Magisk),且本机有 `xhs-mobile-link-collector` 项目

## 架构:两段式(快列表 + 逐篇补全)

```
阶段A  Route-B 抓包主页列表接口 note/user/posted  →  一次20篇,精确 likes/create_time/
       is_goods_note/note_id/图片,全年几分钟(手动或温和自动滑,不限流)
         ↓  本地筛选:likes>N 且 时间在区间 且 is_goods_note 且 标题/正文关键词粗筛
         ↓  (多品类号再逐篇抓 note/widgets 核验 item_id 精确分类,见阶段A.5)
阶段B  对筛出的每篇 note_id:深链 xhsdiscover://item/<id> 直接打开(不需要token)
       → 复制短链(worker._copy_current_note_link)→ 网页版桌面UA解析无水印图+视频
         ↓
       写飞书多维表格 + 转移所有人
```

**为什么两段**:列表接口快但**不含 item_id、不含视频URL、不含 xsec_token**;
逐篇深链开才能拿短链和视频。深链直开比"滚动找卡"快得多,也比逐篇手机取数据快
(数据解析交给网页版)。

## 前置

```bash
PROJ=<工蜂项目目录>   # 或 export WORKERBEE_PROJ=... 后脚本自动读取
SERIAL=<你的设备序列号>          # adb devices 查
ADB=$PROJ/tools/adb              # 项目自带 adb

# 1. 确认 root
$ADB -s $SERIAL shell "su -c id"   # 要有 uid=0

# 2. 一次性装 Route-B 环境(建 mitmproxy venv + 装 CA 到系统证书区)
cd $PROJ && .venv/bin/python scripts/setup_xhs_root_env.py --serial $SERIAL
# ⚠️ 手机重启后系统证书 bind-mount 失效,要重跑这步

# 3. 飞书凭证(建表 + 转所有人):放 $PROJ/.env(已 gitignore)
#    FEISHU_APP_ID / FEISHU_APP_SECRET;转所有人目标 open_id 见 permissions.configured_admin_open_ids
```

关键路径常量:
- mitmproxy: `~/.xhs-root/mitmproxy-venv/bin/mitmdump`
- **confdir(装 CA 的那个,务必用对): `~/.xhs-root/mitmconf`** — 见踩坑#2
- 代理端口 8080,USB 走 `adb reverse tcp:8080 tcp:8080` + `settings put global http_proxy 127.0.0.1:8080`

## 阶段A:抓全年列表

```bash
# 起代理(正确 confdir!)
MITM=~/.xhs-root/mitmproxy-venv/bin/mitmdump; CONF=~/.xhs-root/mitmconf; FLOW=/tmp/rb.mitm
pkill -9 -f mitmdump; rm -f $FLOW
$MITM --listen-host 127.0.0.1 --listen-port 8080 --set confdir=$CONF --set block_global=false -w $FLOW &
sleep 3
$ADB -s $SERIAL reverse tcp:8080 tcp:8080
$ADB -s $SERIAL shell settings put global http_proxy 127.0.0.1:8080
$ADB -s $SERIAL shell settings put secure navigation_mode 0   # 三键导航,防上滑触发最近任务
# 开博主主页(deep-link,uid 从 profile URL 取)
$ADB -s $SERIAL shell am start -a android.intent.action.VIEW -d "xhsdiscover://user/<uid>" com.xingin.xhs
```

然后**滑动**(手动最稳,或温和自动 ~1.3-2s/次;别快甩,见坑#4)。
边滑边解析 `note/user/posted` 响应(每篇字段):`id / title / desc / likes / comments_count /
collected_count / share_count / type(normal|video) / create_time(unix) / is_goods_note /
images_list[].url_size_large`。到目标时间就停。

**收尾必做**:`settings put global http_proxy :0` + `reverse --remove-all` + `pkill mitmdump`。
**代理不清,后面全是空白页(坑#1)。**

解析脚本见 `scripts/parse_posted.py`(本 skill 目录),用 mitmproxy venv 跑。

## 阶段A筛选

- 时间:`create_time >= 区间起点`
- 点赞:`likes > 阈值`(如 100)
- 挂车:`is_goods_note == True`
- 目标商品:列表**没有 item_id**,只能先用标题+正文关键词**粗筛**。先搞清目标商品是什么
  (开一次商品页抓 `mall.../shop_personal_tab` 或 `jpd/edith/detail`,拿商品名),再定关键词。
- **关键词只是近似,不是最终分类**:
  - **单品类号**(只卖一个品,如所有「XX光腿神器」号)→ 直接 `likes>N 且 is_goods_note` 全收,
    别加关键词过滤(会误删标题不写"光腿"的爆款,见坑11)。
  - **多品类号**(同店既卖光腿又卖T恤)→ 关键词会污染(实测混入 42%~66% 的别的品),
    **必须逐篇核验 item_id 才能干净分类**(见下节 + 坑17)。

## 阶段A.5:精确核验挂载商品 item_id(区分同店多品)

列表接口不给 item_id,唯一可靠的分类办法:逐篇深链开笔记 → 抓商品卡接口 `note/widgets`
→ 取真实 itemId。**多品类号或要"确证挂的就是这个商品"时必做这步。**

```python
# 只存 widgets 流,flow 极小
mitmdump ... --set "save_stream_filter=~u note/widgets" -w $FLOW
# 逐篇:深链开 → 小滑一下把商品卡滑进视口(触发 widgets 请求)→ 返回
# verify_itemid.py 会读取 adb shell wm size，优先使用 Override size，再按逻辑视口比例滑动。
python scripts/verify_itemid.py <cand_note_ids.json> <out_map.json>
```

解析:itemId 藏在 `data.goods_card_comment_guide.link` 的 `rate_limit_meta` 里(URL 编码),
正文里同现 `noteId=<24hex>` 和 `itemId%3D<24hex>`(`%3D` 就是 `=`),两者配对即得。
拿到 `{note_id: itemId}` 后,按目标 itemId 过滤/分类,删掉别的品、补回被关键词误删的本品。

完整脚本:`scripts/verify_itemid.py`(增量保存、可续传,每篇约 4s)。

## 阶段B:逐篇补短链+视频(深链直开)

对筛出的每个 note_id:

```python
# 深链直接打开笔记(不需要 xsec_token!见坑#5)
adb("shell","am","start","-a","android.intent.action.VIEW","-d",f"xhsdiscover://item/{nid}","com.xingin.xhs")
time.sleep(3.2)
clip = worker._copy_current_note_link()             # 点···/分享→复制链接→读剪贴板
link = re.search(r'https?://xhslink\.[a-z]+/[A-Za-z0-9/]+', clip).group(0)
info = fetch_note_web_info(link)                     # 桌面UA网页解析:无水印图+视频+正文
video = (info.get("video_urls") or [""])[0]
images = info.get("image_urls")                      # 无水印大图
```

完整可跑脚本:`scripts/backfill_deeplink.py`(本 skill 目录)。带断点续传。
节奏 ~3s/篇,遇失败退避。157篇约40分钟,深链直开成功率≈99%+。

## 阶段B写飞书

- 建表字段全用**文本类型**(用户偏好),链接/封面也是文本,不用 URL 字段类型
- 短链存 `http://xhslink.cn/o/...`(可点)、视频存 masterUrl、图片存无水印大图 URL 换行拼接
- `write_note_rows_to_feishu_base`(项目内)可上传封面为附件防图床过期;
  或直接 batch_create/batch_update 走飞书 bitable API
- **商品ID / 商品名**字段:填阶段A.5 核验出的 itemId 与商品名(多品号靠它分类,单品号也便于核对)
- **视频文件**字段:挂视频附件;大文件走分片上传(见坑18 / `scripts/fill_video_files.py`)
- 建完 `transfer_bitable_owner` 转所有人;交付说明可用 `lark-cli docs +create` 建文档(见坑19)

## 一句话流程

Route-B 抓 `note/user/posted` 拿全年精确列表 → 本地筛(赞/时间/挂车/关键词)→
深链 `xhsdiscover://item/<id>` 逐篇直开 → 复制短链 → 网页版桌面UA解析无水印图+视频 →
写飞书多维表格文本字段 → 转所有人。**每次操作前后清代理。**

---

# 踩坑记录(2026-08-12,血泪)

## 坑1 ⭐残留代理 = 头号大坑,会伪装成一切"能力问题"
mitmdump 停了,但手机 `settings global http_proxy` 还指着 `127.0.0.1:8080`(死端口),
`adb reverse` 也没了 → App **所有网络请求失败** → 页面空白、深链打不开、找不到卡、profile 不加载。
**它半天里伪装成了:"edith 被 pinning""深链需要 token""worker 找不到卡""profile 空白"。**
**铁律:每次抓包收尾必 `settings put global http_proxy :0` + `reverse --remove-all`;
遇到"打不开/空白/找不到"第一件事就是查 `settings get global http_proxy` 是不是 :0。**

## 坑2 confdir 打错一个字 → 误判成 pinning
mitmdump 必须用装 CA 时的 confdir:`~/.xhs-root/mitmconf`。
打成 `~/.xhs-root/mitm-conf`(多个连字符),mitmproxy 会**自生成另一套从没装进手机的 CA**,
→ 全域名 TLS 握手失败(`certificate for edith.xiaohongshu.com ... certificate unknown`)
→ 被误判成"小红书对 edith 做了证书绑定"。**其实 edith 根本没 pinning**,
confdir 用对时全接口解密。判"pinning"前先确认 confdir 和已装 CA 一致。

## 坑3 快速甩会触发限流 461
90ms 硬 fling + 短间隔 → `{"code":300013,"msg":"访问频繁"}`,手机弹"采集频繁"警告。
**真人节奏 / 温和自动滑(~1.3-2s/次)不触发。** 被限后要冷却几分钟。
用户实测:手动滑从不限流。

## 坑4 深链不需要 token(之前误判)
`xhsdiscover://item/<note_id>` 直接打开笔记详情,**不需要 xsec_token**。
之前测"深链打不开"其实是坑1(残留代理)。深链直开是阶段B的关键提速点——
不用滚动找卡、不用逐篇匹配标题。

## 坑5 短链/token 不在数据里,是"动作"产物
- 列表接口 `note/user/posted`、详情接口 imagefeed **都不含 xsec_token**(App 用签名请求,不走URL token)。
- 想要能点开的链接只能靠 App"分享→复制链接"动作生成的 `xhslink.cn` 短链
  (`worker._copy_current_note_link` 读剪贴板)。
- `explore/{note_id}` 拼出来的链接**没 token,网页打开是空页、点不开**。

## 坑6 列表接口给什么、不给什么
`note/user/posted` **给**:likes/comments/collect/share(精确整数)、create_time、
is_goods_note、note_id、images_list、desc。**不给**:商品 item_id、视频URL、xsec_token。
所以精确"挂某商品"匹配要逐篇开笔记抓 `note/widgets`(拿 itemId,见阶段A.5);快速近似才用关键词。
(响应里出现 "goods_card" 是 `advanced_widgets_groups` 的抓取类型名,不是真数据,别误判有 item_id。)

## 坑7 u2 的 dump 在某些设备不稳,且与 raw dump 冲突
搜狗录音笔(E2_AI_Recorder)上 uiautomator2 的 `dump_hierarchy`/`_find_profile_note_card_centers`
经常返回空或抓不到卡;raw `adb shell uiautomator dump` 更可靠。
**但同时只能有一个 uiautomator 实例**:创建 MobileWorker(启动 u2 服务)后再 `adb uiautomator dump` 会冲突。
用深链直开(阶段B)后,不再需要滚动找卡,这个冲突就绕过去了。

## 坑8 屏幕手势 / 特殊设备
- 上滑可能被系统当"进最近任务",把 App 弹走 → `settings put secure navigation_mode 0`(三键)+
  滑动限制在安全中段(y 从 ~560 到 ~240,避开上下边缘)。
- 录音笔:物理 480x800、overscan 70px、density 被覆盖(190 vs 251);raw dump/screencap 是 340x800 空间。

## 坑9 剪贴板读取依赖 u2
`worker._read_clipboard` 用 `device.clipboard`(u2/atx-agent),复制短链这步必须有 u2。
深链开笔记用 adb(am start),复制用 worker(u2),两者不冲突(am start 不是 uiautomator dump)。

## 坑10 断点续传要有
逐篇 40 分钟的活,中途手机 USB 会掉、会限流。用 `done.json` 记已完成的 note_id,
每 N 篇存一次,中断重跑自动跳过已完成。飞书 token 也要定期刷新(每10篇重取)。

---

# 踩坑记录(2026-08-13,批量5博主时新增)

## 坑11 ⭐单品号要放宽筛选,别用"排除其他品类关键词"
若博主是**单品牌单品类号**(如所有「XX光腿神器」号只卖光腿神器),筛选就用
`likes>N 且 is_goods_note`,**不要**再加"标题/正文必须命中光腿词"或"排除T恤词"——
实测很多明显是光腿神器的爆款笔记标题只写「720针莱卡」「防勾丝」「实况直出」「不掉档」,
不写"光腿",会被关键词过滤误删(某博主 59 篇里误删 10 篇全是光腿)。
关键词过滤只在**多品类号**(既卖光腿又卖T恤,如「某品牌光腿神器5」)时才需要,用来区分品类。
先判断这个号是单品还是多品,再决定用不用关键词。

## 坑12 捕获脚本:开局多等 + 无新增就停
- **开局 profile 没加载完就滑 → 卡在第1页(20篇 has_more=True 但滚不动)。** 深链开主页后
  等 7-8 秒再滚(不是 5 秒)。判断:第一次外部解析若只有 1 页且 has_more=True,多半是没加载完。
- 停止条件必须有"连续 N 次(如4)无新增笔记就停"(到底了),否则勤更号会一直空滚到 600 屏上限;
  低产号(几十篇)也能靠这个及时停。别只靠"过一年线"早停(有的号最老笔记还没到一年线就没了)。

## 坑13 超长抓取后 u2/App 状态变差 → 回填批量失败
抓 2000+ 篇(flow 100MB+、滚 480+ 次)后,紧接着回填会**成功率骤降**(60篇只成1篇),
但深链能开、代理干净、单篇手动测又成功——是 u2/atx-agent 或 App 累了。
**解法:回填前 `am force-stop com.xingin.xhs` 重启 App 清状态**,再跑就恢复 100%。
回填脚本已有 5 连败退避 20s,但这种"整体退化"退避救不了,必须重启 App。

## 坑14 飞书 batch_update 返回错误不抛异常 → 误记 done
`fapi` 出错时返回错误 dict 而非抛异常,回填脚本会以为成功、`done.add(nid)`,
但表里那条其实没更新(还留着旧的 explore 链接)。**最后必须按"笔记链接是否 xhslink"复核补漏**:
查表里 `博主=X 且 链接非 xhslink` 的记录,清掉它们的 done 记录强制重跑。
更稳的做法:回填时检查 `resp.get("code")==0` 才 `done.add`。

## 坑15 里程碑解析大 flow 是 O(n²),会很慢
捕获脚本每 8 屏重读整个 flow 解析一次;flow 到 100MB+(勤更号一年 2000+ 篇)时
每次解析 30s+,拖慢整个循环、里程碑输出也被 python 缓冲看不到(用外部独立解析看真实进度)。
可优化为增量解析(记录已读 flow 偏移),但一次性任务能忍。

## 坑16 粉丝赞数 ≠ 笔记量,别按赞数预期篇数
2M 赞的号可能只有 32 篇/年(靠一条 18.7万赞爆款),83.8K 的号反而 1177 篇/年。
低产爆款号筛出来可能就 1-2 篇,是真实的,不是抓漏——用坑12的"无新增就停"+核对日期分布确认。

---

# 踩坑记录(2026-08-13,item_id 核验 + 补视频文件时新增)

## 坑17 ⭐多品类号靠关键词分类会污染,必须 item_id 核验
坑11 讲单品号要放宽(别用关键词);反面是:**多品类号(同店既卖光腿又卖T恤)绝不能只靠关键词**。
实测对多品号用"无关键词全收"→ 混入 42%~66% 的别的品(T恤当光腿收了);用关键词又漏掉
标题不写品名的本品。**唯一干净解:逐篇抓 `note/widgets` 拿 itemId,按目标 itemId 分类**
(见阶段A.5 / `scripts/verify_itemid.py`)。先判单品还是多品:单品放宽,多品核验 itemId。
核验产出 `{note_id: itemId}` 后据此修表——删非目标品、补回被误删的本品、回填商品ID/商品名。

## 坑18 补视频文件附件:大文件分片 + 响应正则 + 单条也走 batch_update
"视频链接有、但视频附件为空"多因飞书「链接转附件」捷径处理不了大文件(>20MB)。程序化补时三个坑:
- **大文件**:`medias/upload_all` 只适合 ≤20MB;超过要 `upload_prepare → upload_part(逐块)→
  upload_finish` 分片链路(实测 51.5MB/30.5MB 靠这条补上)。
- **响应解析**:飞书上传响应带 chunked 传输残留,`r.json()` 抛 `Extra data`;
  必须正则从 `r.text` 抠 `file_token`/`upload_id`/`block_size`/`block_num`。
- **单条更新**:更新一条记录也用 `POST /records/batch_update`(records 数组包一条);
  用 `POST /records/{record_id}` 会 404 page not found。
完整脚本:`scripts/fill_video_files.py`(带续传)。

## 坑19 交付说明文档:多维表格不能内嵌文档,只能反向
想把"数据采集说明"落成飞书云文档,用 `lark-cli docs +create --content @doc.xml`(XML 默认格式,
表格用标准 `<table>`,末尾可加 `<bookmark href=表链接>` 回链)。但**多维表格(bitable/base)块
「仅支持移动,不可创建」**——不能用 API 把一篇文档作为页面塞进多维表格里(只能反过来:文档内嵌表)。
所以做法是独立建文档 + 互链;要"表里看得见"得在飞书界面手动拖链接。
另注:别把 `docs +create` 写成管道拼接,容易误触发两次创建出重复文档(用 `+search` 查重、`drive +delete` 清)。

---

# 复盘一句话

**这类"打不开/空白/找不到卡/像被 pinning"的怪象,90% 是坑1(残留代理)或坑2(confdir 打错)。
先查这两个,再怀疑能力。用户在整场里坚持的方向(手动滑不限流、网页版解析、深链直开)全部正确,
弯路都来自这两个隐蔽的环境状态。**
