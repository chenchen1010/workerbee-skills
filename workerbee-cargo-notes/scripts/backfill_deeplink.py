#!/usr/bin/env python3
"""阶段B:对筛出的 note_id 列表,深链逐篇直开 → 复制短链 → 网页版解析无水印图+视频 → 回写飞书。

在 xhs-mobile-link-collector 项目根用项目 venv 跑(要 import app.*):
    PYTHONPATH=<PROJ> <PROJ>/.venv/bin/python backfill_deeplink.py

配置改下面 CONFIG 段。带断点续传(done.json),中断重跑自动跳过。

核心成功要点(见 SKILL.md 踩坑):
- 深链 xhsdiscover://item/<id> 直接开笔记,不需要 xsec_token(坑4)
- 短链来自"复制链接"动作(worker._copy_current_note_link),不在任何接口数据里(坑5)
- 数据解析交给网页版 fetch_note_web_info(桌面UA→无水印图+视频),不在手机上取
- 开笔记用 adb(am start),复制用 worker(u2),两者不冲突(坑9)
- 运行前后确保手机无残留代理(坑1):settings put global http_proxy :0
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
import os
from pathlib import Path

# ==== CONFIG ====
SERIAL = "<设备序列号>"
ADB = str(Path(os.environ.get("WORKERBEE_PROJ") or (Path.home() / "Desktop/Code/小红书工作台/xhs-mobile-link-collector")) / "tools/adb")
NOTE_IDS_JSON = "<筛出的note_id列表.json>"   # 一个 note_id 字符串数组,或 {note_id: record_id} 映射
PROGRESS = "/tmp/xhs_backfill_done.json"
FEISHU_APP = "<FEISHU_APP_ID>"
FEISHU_SEC = "<FEISHU_APP_SECRET>"
BASE_TOKEN = "<多维表格 app_token>"
TABLE_ID = "<table_id>"
# 表字段名(全文本类型)
F_LINK, F_VIDEO, F_COVER, F_IMGS = "笔记链接", "视频链接", "封面图", "图片链接"
# ================

from app.collectors.xhs_mobile.worker import MobileWorker, WorkerConfig  # noqa: E402
from app.collectors.xhs_mobile.goods_parser import fetch_note_web_info    # noqa: E402


def adb(*a):
    return subprocess.run([ADB, "-s", SERIAL, *a], capture_output=True, text=True, timeout=60).stdout


def ftok():
    r = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": FEISHU_APP, "app_secret": FEISHU_SEC}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=15).read())["tenant_access_token"]


def fapi(method, path, t, body=None):
    r = urllib.request.Request(
        "https://open.feishu.cn/open-apis" + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"}, method=method)
    try:
        return json.loads(urllib.request.urlopen(r, timeout=25).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def main() -> int:
    raw = json.load(open(NOTE_IDS_JSON))
    rec_map = raw if isinstance(raw, dict) else {nid: None for nid in raw}
    try:
        done = set(json.load(open(PROGRESS)))
    except Exception:
        done = set()
    todo = [nid for nid in rec_map if nid not in done]
    print(f"目标 {len(rec_map)} 篇, 待办 {len(todo)}", flush=True)

    adb("shell", "settings", "put", "global", "http_proxy", ":0")   # 坑1:先清代理
    w = MobileWorker(WorkerConfig(serial=SERIAL, keyword="", limit=0, db_path="xhs_links.db"))
    ft = ftok()
    filled = 0
    fails = 0
    for i, nid in enumerate(todo):
        adb("shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"xhsdiscover://item/{nid}", "com.xingin.xhs")   # 坑4:深链直开,无需 token
        time.sleep(3.2)
        try:
            clip = w._copy_current_note_link()                    # 坑5/9:复制短链(u2 读剪贴板)
            m = re.search(r"https?://xhslink\.[a-z]+/[A-Za-z0-9/]+", clip)
            if not m:
                raise RuntimeError("no shortlink")
            link = m.group(0)
            info = fetch_note_web_info(link)                      # 网页版桌面UA解析
            vids = info.get("video_urls") or []
            imgs = info.get("image_urls") or []
            fields = {F_LINK: link}
            if vids:
                fields[F_VIDEO] = vids[0]
            if info.get("cover_image_url"):
                fields[F_COVER] = info["cover_image_url"]
            if imgs:
                fields[F_IMGS] = "\n".join(imgs)[:2000]
            rid = rec_map.get(nid)
            if rid:
                fapi("POST", f"/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records/batch_update",
                     ft, {"records": [{"record_id": rid, "fields": fields}]})
            filled += 1
            done.add(nid)
            fails = 0
        except Exception:
            fails += 1
            if fails >= 5:                                        # 坑3:连续失败疑似限流,退避
                print("  连续失败,退避 20s", flush=True)
                time.sleep(20)
                fails = 0
        if (i + 1) % 10 == 0:
            json.dump(list(done), open(PROGRESS, "w"))            # 坑10:断点续传
            ft = ftok()                                          # 定期刷 token
            print(f"  {i + 1}/{len(todo)} 已回填 {filled}", flush=True)
        adb("shell", "input", "keyevent", "4")                   # 返回
        time.sleep(0.8)
    json.dump(list(done), open(PROGRESS, "w"))
    print(f"完成:本轮回填 {filled},累计 {len(done)}/{len(rec_map)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
