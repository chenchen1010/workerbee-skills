#!/usr/bin/env python3
"""精确核验:逐篇打开笔记读商品卡 itemId(区分同店多个商品)。

列表接口 note/user/posted 不含 item_id(坑6),关键词近似在多品类号上会污染(坑17);
唯一可靠的分类办法是逐篇开笔记、抓商品卡接口 note/widgets、从里面取真实 itemId。

用 mitmproxy venv 起代理即可(不 import 项目),深链开笔记用 adb:
    python verify_itemid.py <cand_note_ids.json> <out_map.json>
    # 入:note_id 字符串数组;出:{note_id: itemId} 映射(增量保存,可续传)

要点:
- 只存 note/widgets 流(`--set save_stream_filter=~u note/widgets`),flow 极小、解析快。
- itemId 藏在 data.goods_card_comment_guide.link 的 rate_limit_meta 里,URL 编码:
  正文出现 `noteId=<24hex>` 和 `itemId%3D<24hex>`(%3D 就是 =)。两者同现才配对。
- 开笔记后小滑一下(swipe)把商品卡滑进视口,才会触发 widgets 请求。
- 每篇约 4s。中断重跑靠 out_map 已有的 note_id 跳过。
"""
import json
import re
import subprocess
import sys
import time
import os
from pathlib import Path

# ==== CONFIG ====
SERIAL = "<设备序列号>"
ADB = str(Path(os.environ.get("WORKERBEE_PROJ") or (Path.home() / "Desktop/Code/小红书工作台/xhs-mobile-link-collector")) / "tools/adb")
MITM = str(Path.home() / ".xhs-root/mitmproxy-venv/bin/mitmdump")
MITMPY = str(Path.home() / ".xhs-root/mitmproxy-venv/bin/python")
CONF = str(Path.home() / ".xhs-root/mitmconf")   # 坑2:必须是装 CA 的那个 confdir
FLOW = "/tmp/vitem.mitm"
# ================

CAND, OUT = sys.argv[1], sys.argv[2]


def adb(*a):
    return subprocess.run([ADB, "-s", SERIAL, *a], capture_output=True, text=True, timeout=60).stdout


PARSE = r'''
import json, sys, re
from mitmproxy.io import FlowReader
res = {}
try:
    with open(sys.argv[1], "rb") as f:
        for fl in FlowReader(f).stream():
            if not hasattr(fl, "request") or not fl.response or "note/widgets" not in fl.request.path:
                continue
            body = fl.response.content.decode("utf-8", "replace")
            nid = re.search(r"noteId=([0-9a-f]{24})", body)
            iid = re.search(r"itemId%3D([0-9a-f]{24})", body)
            if nid and iid:
                res[nid.group(1)] = iid.group(1)
except Exception:
    pass
json.dump(res, open(sys.argv[2], "w"))
'''


def main() -> int:
    cand = json.load(open(CAND))
    try:
        res = json.load(open(OUT))
    except Exception:
        res = {}
    todo = [n for n in cand if n not in res]
    print(f"核验 {len(cand)} 篇, 待办 {len(todo)}", flush=True)
    if not todo:
        print("已全部核验")
        return 0

    subprocess.run(["pkill", "-9", "-f", "mitmdump"], capture_output=True)
    time.sleep(1)
    Path(FLOW).unlink(missing_ok=True)
    mp = subprocess.Popen(
        [MITM, "--listen-host", "127.0.0.1", "--listen-port", "8080",
         "--set", f"confdir={CONF}", "--set", "block_global=false",
         "--set", "save_stream_filter=~u note/widgets", "-w", FLOW],
        stdout=open("/tmp/vitem.log", "wb"), stderr=subprocess.STDOUT)
    time.sleep(3)
    adb("reverse", "tcp:8080", "tcp:8080")
    adb("shell", "settings", "put", "global", "http_proxy", "127.0.0.1:8080")
    adb("shell", "am", "force-stop", "com.xingin.xhs")
    time.sleep(1)

    def parse_merge():
        subprocess.run([MITMPY, "-c", PARSE, FLOW, "/tmp/vitem_p.json"], capture_output=True)
        try:
            res.update(json.load(open("/tmp/vitem_p.json")))
            json.dump(res, open(OUT, "w"))
        except Exception:
            pass

    for i, nid in enumerate(todo):
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"xhsdiscover://item/{nid}", "com.xingin.xhs")   # 坑4:深链直开,无需 token
        time.sleep(2.4)
        adb("shell", "input", "swipe", "170", "520", "170", "330", "250")  # 把商品卡滑进视口
        time.sleep(1.0)
        adb("shell", "input", "keyevent", "4")   # 返回
        time.sleep(0.5)
        if (i + 1) % 20 == 0:
            parse_merge()
            print(f"  {i + 1}/{len(todo)} 已解析 itemId {len(res)}", flush=True)

    adb("shell", "settings", "put", "global", "http_proxy", ":0")   # 坑1:收尾清代理
    adb("reverse", "--remove-all")
    mp.terminate()
    time.sleep(2)
    parse_merge()
    print(f"完成: 核验 itemId {len(res)}/{len(cand)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
