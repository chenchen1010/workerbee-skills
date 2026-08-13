#!/usr/bin/env python3
"""阶段A解析:从 mitmproxy flow 里抽出博主主页笔记列表(note/user/posted)。

用 mitmproxy venv 跑(它有 mitmproxy 依赖):
    ~/.xhs-root/mitmproxy-venv/bin/python parse_posted.py <flow.mitm> <out.json> [cutoff_ts]

输出:按 create_time 倒序的笔记列表,每篇含
    id / title / desc / likes / comments_count / collected_count / share_count /
    type / create_time / is_goods_note / images_list
用户侧再做筛选(likes>N、时间区间、is_goods_note、关键词)。
"""
import json
import sys

from mitmproxy.io import FlowReader


def main() -> int:
    flow_path = sys.argv[1]
    out_path = sys.argv[2]
    notes = {}
    limited = 0
    with open(flow_path, "rb") as f:
        for fl in FlowReader(f).stream():
            if not hasattr(fl, "request") or not fl.response:
                continue
            if "note/user/posted" not in fl.request.path:
                continue
            try:
                d = json.loads(fl.response.content.decode("utf-8", "replace"))
            except Exception:
                continue
            if d.get("code") == 300013:      # 访问频繁 = 限流(见坑#3)
                limited += 1
                continue
            for n in (d.get("data") or {}).get("notes") or []:
                if n.get("id"):
                    notes[n["id"]] = n
    rows = sorted(notes.values(), key=lambda n: n.get("create_time", 0), reverse=True)
    json.dump(rows, open(out_path, "w"), ensure_ascii=False)
    goods = sum(1 for n in rows if n.get("is_goods_note"))
    print(f"解析 {len(rows)} 篇 (挂车 {goods});限流响应 {limited} 个 → {out_path}")
    if rows:
        import datetime
        d = lambda ts: datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "?"
        print(f"时间跨度 {d(rows[-1]['create_time'])} → {d(rows[0]['create_time'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
