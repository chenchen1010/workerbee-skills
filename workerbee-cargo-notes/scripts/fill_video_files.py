#!/usr/bin/env python3
"""补视频文件附件:把「有视频链接、但视频附件为空」的记录,下载视频并转存为飞书附件。

场景:飞书「链接转附件」捷径处理不了大文件(>20MB),这些笔记视频字段会缺文件。
本脚本把 masterUrl 下载下来,按大小选普通/分片上传到多维表格,再挂到「视频文件」字段。

在项目根用项目 venv 跑(需 requests,凭证读 .env):
    PYTHONPATH=<PROJ> <PROJ>/.venv/bin/python fill_video_files.py <need_video.json>
    # need_video.json: {record_id: 视频masterUrl} 映射

三个真踩过的坑:
- 坑A 大文件:medias/upload_all 只适合 ≤20MB;超过要走
       upload_prepare → upload_part(逐块)→ upload_finish 分片链路。
- 坑B 响应解析:飞书上传响应带 chunked 传输残留,r.json() 抛 "Extra data";
       必须用正则从 r.text 里抠 file_token / upload_id / block_size / block_num。
- 坑C 单条更新:更新一条记录用 POST /records/batch_update(records 数组包一条),
       用 POST /records/{record_id} 会 404 page not found。
带断点续传(video_done.json),每 5 条存一次并刷 token。
"""
import json
import re
import sys
import os
from pathlib import Path

import requests

# ==== CONFIG ====
PROJ = Path(os.environ.get("WORKERBEE_PROJ") or (Path.home() / "Desktop/Code/小红书工作台/xhs-mobile-link-collector"))
BASE = "<多维表格 app_token>"
TID = "<table_id>"
DONE = "/tmp/xhs_video_done.json"
F_VIDEO_FILE = "视频文件"
# ================


def env(k):
    for line in open(PROJ / ".env"):
        if line.startswith(k + "="):
            return line.split("=", 1)[1].strip()


APP, SEC = env("FEISHU_APP_ID"), env("FEISHU_APP_SECRET")


def tok():
    return requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP, "app_secret": SEC}, timeout=15).json()["tenant_access_token"]


def _grab(pat, text):
    m = re.search(pat, text)
    return m.group(1) if m else None


def upload_all(t, data, name):   # ≤20MB
    r = requests.post(
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {t}"},
        data={"file_name": name, "parent_type": "bitable_file", "parent_node": BASE, "size": str(len(data))},
        files={"file": (name, data, "video/mp4")}, timeout=180)
    return _grab(r'"file_token"\s*:\s*"([^"]+)"', r.text)   # 坑B:正则,不用 r.json()


def upload_chunked(t, data, name):   # >20MB
    r = requests.post(
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_prepare",
        headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"},
        json={"file_name": name, "parent_type": "bitable_file", "parent_node": BASE, "size": len(data)}, timeout=30)
    uid = _grab(r'"upload_id"\s*:\s*"([^"]+)"', r.text)
    bs = int(_grab(r'"block_size"\s*:\s*(\d+)', r.text) or 0)
    bn = int(_grab(r'"block_num"\s*:\s*(\d+)', r.text) or 0)
    if not uid:
        print("  prepare 失败", r.text[:80]); return None
    for seq in range(bn):
        chunk = data[seq * bs:(seq + 1) * bs]
        pr = requests.post(
            "https://open.feishu.cn/open-apis/drive/v1/medias/upload_part",
            headers={"Authorization": f"Bearer {t}"},
            data={"upload_id": uid, "seq": str(seq), "size": str(len(chunk))},
            files={"file": (name, chunk, "application/octet-stream")}, timeout=180)
        if '"code":0' not in pr.text:
            print(f"  part{seq} 失败", pr.text[:80]); return None
    fr = requests.post(
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_finish",
        headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"},
        json={"upload_id": uid, "block_num": bn}, timeout=60)
    return _grab(r'"file_token"\s*:\s*"([^"]+)"', fr.text)


def main() -> int:
    need = json.load(open(sys.argv[1]))
    try:
        done = set(json.load(open(DONE)))
    except Exception:
        done = set()
    todo = [(r, u) for r, u in need.items() if r not in done]
    print(f"补视频文件 {len(todo)}/{len(need)}", flush=True)
    t = tok()
    ok = 0
    for i, (rid, url) in enumerate(todo):
        try:
            vid = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=180).content
            mb = len(vid) / 1048576
            ft = upload_chunked(t, vid, "note.mp4") if len(vid) > 19 * 1048576 else upload_all(t, vid, "note.mp4")
            if not ft:
                print(f"  [{i + 1}] {mb:.1f}MB 上传失败", flush=True); continue
            up = requests.post(   # 坑C:单条也走 batch_update
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{TID}/records/batch_update",
                headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"},
                json={"records": [{"record_id": rid, "fields": {F_VIDEO_FILE: [{"file_token": ft}]}}]}, timeout=30)
            if '"code":0' in up.text:
                ok += 1; done.add(rid); print(f"  [{i + 1}] {mb:.1f}MB ✓", flush=True)
            else:
                print(f"  [{i + 1}] 挂字段失败 {up.text[:80]}", flush=True)
        except Exception as e:
            print(f"  [{i + 1}] 异常 {str(e)[:60]}", flush=True)
        if (i + 1) % 5 == 0:
            json.dump(list(done), open(DONE, "w"))
            t = tok()
    json.dump(list(done), open(DONE, "w"))
    print(f"完成 {ok}/{len(todo)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
