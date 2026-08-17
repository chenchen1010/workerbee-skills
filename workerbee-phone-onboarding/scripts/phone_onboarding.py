#!/usr/bin/env python3
"""Diagnose and run WorkerBee's packaged first-phone onboarding flow."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def discovery_candidates(explicit: str = "") -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_path = os.getenv("WORKERBEE_DISCOVERY_FILE", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.getenv("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    candidates.extend(root / name / "api.json" for name in ("工蜂客户版", "工蜂"))

    unique = {str(path): path for path in candidates}
    return sorted(
        unique.values(),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )


def read_discovery(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    base_url = str(data.get("base_url") or "").rstrip("/")
    key = str(data.get("key") or "")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("discovery base_url is not a local loopback HTTP address")
    if not key:
        raise ValueError("discovery file has no key")
    return {"base_url": base_url, "key": key, "path": str(path)}


def request_json(
    config: dict[str, Any], path: str, *, method: str = "GET", body: dict | None = None
) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        config["base_url"] + path,
        data=payload,
        headers={"X-Api-Key": config["key"], "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"ok": False, "error": f"HTTP {exc.code}"}
        data.setdefault("http_status", exc.code)
        return data


def connect(explicit: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    errors = []
    for path in discovery_candidates(explicit):
        if not path.exists():
            continue
        try:
            config = read_discovery(path)
            wizard = request_json(config, "/api/device-wizard/status")
            if wizard.get("ok") is not False:
                return config, wizard
            errors.append(f"{path}: {wizard.get('error', 'unavailable')}")
        except Exception as exc:
            errors.append(f"{path}: {type(exc).__name__}: {str(exc)[:120]}")
    suffix = "; " + "; ".join(errors) if errors else ""
    raise RuntimeError("未找到正在运行的工蜂本机接口" + suffix)


def get_wizard(config: dict[str, Any], serial: str = "") -> dict[str, Any]:
    suffix = "?serial=" + urllib.parse.quote(serial, safe="") if serial else ""
    return request_json(config, "/api/device-wizard/status" + suffix)


def get_detail(config: dict[str, Any], serial: str) -> dict[str, Any]:
    if not serial:
        return {}
    return request_json(
        config,
        "/api/local/devices/" + urllib.parse.quote(serial, safe="") + "/detail",
    )


def diagnose(wizard: dict[str, Any], detail: dict[str, Any]) -> tuple[list[str], list[str]]:
    diagnosis: list[str] = []
    steps: list[str] = []
    checks = wizard.get("checks") or {}
    devices = wizard.get("devices") or []
    adb_state = str(wizard.get("adb_state") or "")
    smoke = checks.get("smoke") or {}
    error = str(smoke.get("error") or (detail.get("health") or {}).get("last_error") or "")

    if not wizard.get("adb_available"):
        diagnosis.append("bundled_adb_unavailable")
        steps.append("重新安装完整的工蜂安装包；不要临时下载项目源码。")
    elif not devices:
        diagnosis.append("usb_device_not_found")
        steps.append("换用可传数据的 USB 线/接口，手机 USB 用途选“文件传输”。")
    elif adb_state and adb_state != "device":
        diagnosis.append("adb_" + adb_state)
        if adb_state == "unauthorized":
            steps.append("解锁手机，在 USB 调试授权弹窗勾选“始终允许”并点允许。")

    if checks.get("xhs_app") and not checks["xhs_app"].get("ok"):
        diagnosis.append("xiaohongshu_not_installed")
        steps.append("从正式渠道安装小红书并登录。")
    if checks.get("components") and not checks["components"].get("ok"):
        diagnosis.append("input_component_missing")

    if "INSTALL_FAILED_USER_RESTRICTED" in error or "adb_keyboard_install_blocked" in error:
        diagnosis.append("miui_usb_install_blocked")
        steps.append(
            "小米/Redmi/MIUI/HyperOS：在开发者选项开启「USB 调试（安全设置）」"
            "和「通过 USB 安装」，重插数据线后再执行 provision。"
        )
    if "nuitka_resource_reader_files" in error:
        diagnosis.append("outdated_workerbee_package")
        steps.append("升级到包含 Nuitka PathLike 推送修复的新版工蜂安装包。")
    if smoke.get("state") == "running":
        diagnosis.append("self_check_running")

    return list(dict.fromkeys(diagnosis)), list(dict.fromkeys(steps))


def summary(config: dict[str, Any], wizard: dict[str, Any]) -> dict[str, Any]:
    serial = str(wizard.get("serial") or "")
    detail = get_detail(config, serial) if serial else {}
    diagnosis, steps = diagnose(wizard, detail)
    smoke = (wizard.get("checks") or {}).get("smoke") or {}
    health = detail.get("health") or {}
    collection_capable = bool(health.get("collection_capable"))
    ready = smoke.get("state") == "passed" and collection_capable
    return {
        "ok": True,
        "ready": ready,
        "serial": serial,
        "adb_available": bool(wizard.get("adb_available")),
        "adb_state": wizard.get("adb_state", ""),
        "devices": wizard.get("devices") or [],
        "checks": wizard.get("checks") or {},
        "collection_capable": collection_capable,
        "diagnosis": diagnosis,
        "next_steps": steps,
        "discovery_file": config["path"],
    }


def print_result(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="WorkerBee first-phone onboarding")
    parser.add_argument("--discovery", default="", help="path to WorkerBee api.json")
    sub = parser.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status", help="read-only onboarding status")
    status_parser.add_argument("--serial", default="")
    provision_parser = sub.add_parser("provision", help="install bundled component and run full smoke")
    provision_parser.add_argument("--serial", default="")
    provision_parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    try:
        config, initial = connect(args.discovery)
        wizard = get_wizard(config, args.serial) if args.serial else initial
        if args.command == "status":
            payload = summary(config, wizard)
            print_result(payload)
            return 0 if payload["ready"] else 2

        serial = str(args.serial or wizard.get("serial") or "").strip()
        if not serial:
            raise RuntimeError("没有可配置的设备；请先连接手机并通过 USB 调试授权")
        devices = wizard.get("devices") or []
        if len(devices) > 1 and not args.serial:
            raise RuntimeError("同时连接多台手机时必须显式传 --serial")

        started_at = int(time.time())
        action = request_json(config, "/api/device-provision", method="POST", body={"serial": serial})
        if not action.get("ok"):
            print_result({"ok": False, "serial": serial, "error": action.get("error", "provision failed")})
            return 1

        deadline = time.time() + max(10, args.timeout)
        seen_running = False
        while time.time() < deadline:
            wizard = get_wizard(config, serial)
            smoke = (wizard.get("checks") or {}).get("smoke") or {}
            state = smoke.get("state")
            seen_running = seen_running or state == "running"
            finished_at = int(smoke.get("at") or 0)
            if state in {"passed", "failed"} and (seen_running or finished_at >= started_at):
                payload = summary(config, wizard)
                payload["provision"] = action
                print_result(payload)
                return 0 if payload["ready"] else 2
            time.sleep(2)

        payload = summary(config, get_wizard(config, serial))
        payload["ok"] = False
        payload["error"] = "provision timed out"
        print_result(payload)
        return 2
    except Exception as exc:
        print_result({"ok": False, "error": f"{type(exc).__name__}: {str(exc)}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
