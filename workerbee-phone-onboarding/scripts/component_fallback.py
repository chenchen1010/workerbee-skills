#!/usr/bin/env python3
"""Auditable fallback installer for WorkerBee's Android helper components."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = SKILL_DIR / "assets"
MANIFEST_PATH = ASSETS_DIR / "manifest.json"
ADB_KEYBOARD_PACKAGE = "com.android.adbkeyboard"
ADB_KEYBOARD_IME = "com.android.adbkeyboard/.AdbIME"
U2_DEVICE_PATH = "/data/local/tmp/u2.jar"


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets(names: list[str] | None = None) -> dict[str, Any]:
    manifest = load_manifest()
    records = manifest.get("assets") or {}
    selected = names or list(records)
    output: dict[str, Any] = {}
    all_ok = True
    for name in selected:
        record = records.get(name) or {}
        path = ASSETS_DIR / name
        exists = path.is_file()
        actual_size = path.stat().st_size if exists else 0
        actual_sha = sha256_file(path) if exists else ""
        ok = (
            exists
            and actual_size == int(record.get("bytes") or -1)
            and actual_sha == str(record.get("sha256") or "")
        )
        all_ok = all_ok and ok
        output[name] = {
            "ok": ok,
            "path": str(path),
            "bytes": actual_size,
            "sha256": actual_sha,
            "source": record.get("source_release") or record.get("source_repo") or "",
            "license": record.get("license") or "",
        }
    return {"ok": all_ok, "assets": output, "manifest": str(MANIFEST_PATH)}


def adb_candidates(explicit: str = "") -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_path = os.getenv("WORKERBEE_ADB", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())
    system_adb = shutil.which("adb")
    if system_adb:
        candidates.append(Path(system_adb))

    if sys.platform == "darwin":
        for app_name in ("WorkerBeeClient.app", "WorkerBee.app"):
            candidates.append(
                Path("/Applications") / app_name / "Contents" / "Resources" / "core" / "tools" / "adb"
            )
    elif os.name == "nt":
        roots = [
            os.getenv("LOCALAPPDATA", ""),
            os.getenv("ProgramFiles", ""),
            os.getenv("ProgramFiles(x86)", ""),
        ]
        for raw_root in roots:
            if not raw_root:
                continue
            root = Path(raw_root)
            candidates.extend(
                [
                    root / "Programs" / "WorkerBee" / "resources" / "core" / "tools" / "adb.exe",
                    root / "WorkerBee" / "resources" / "core" / "tools" / "adb.exe",
                ]
            )

    unique: dict[str, Path] = {}
    for path in candidates:
        unique.setdefault(os.path.normcase(str(path)), path)
    return list(unique.values())


def find_adb(explicit: str = "") -> str:
    for candidate in adb_candidates(explicit):
        if candidate.is_file():
            return str(candidate)
    return ""


def run_adb(
    adb: str,
    args: list[str],
    *,
    serial: str = "",
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    command = [adb]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def list_devices(adb: str) -> list[dict[str, str]]:
    result = run_adb(adb, ["devices"])
    devices: list[dict[str, str]] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def resolve_serial(adb: str, requested: str) -> str:
    devices = list_devices(adb)
    if requested:
        match = next((item for item in devices if item["serial"] == requested), None)
        if match is None:
            raise RuntimeError("指定手机不在 adb devices 列表中")
        if match["state"] != "device":
            raise RuntimeError(f"手机尚未授权 USB 调试：{match['state']}")
        return requested
    authorized = [item["serial"] for item in devices if item["state"] == "device"]
    if len(authorized) == 1:
        return authorized[0]
    if len(authorized) > 1:
        raise RuntimeError("同时连接多台手机时必须显式传 --serial")
    if devices:
        raise RuntimeError(f"手机尚未授权 USB 调试：{devices[0]['state']}")
    raise RuntimeError("没有发现安卓手机；请检查数据线和 USB 用途")


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def shell_text(adb: str, serial: str, args: list[str], timeout: int = 20) -> str:
    return combined_output(run_adb(adb, ["shell", *args], serial=serial, timeout=timeout))


def component_status(adb: str, serial: str) -> dict[str, Any]:
    package = run_adb(
        adb,
        ["shell", "pm", "path", ADB_KEYBOARD_PACKAGE],
        serial=serial,
    )
    ime_list = shell_text(adb, serial, ["ime", "list", "-s"])
    u2_exists = run_adb(
        adb,
        ["shell", "test", "-f", U2_DEVICE_PATH],
        serial=serial,
    ).returncode == 0
    remote_sha = ""
    if u2_exists:
        sha_result = shell_text(adb, serial, ["sha256sum", U2_DEVICE_PATH])
        first = sha_result.split()[0] if sha_result.split() else ""
        remote_sha = first if len(first) == 64 else ""
    manufacturer = shell_text(adb, serial, ["getprop", "ro.product.manufacturer"]).strip()
    model = shell_text(adb, serial, ["getprop", "ro.product.model"]).strip()
    return {
        "ok": True,
        "serial": serial,
        "manufacturer": manufacturer,
        "model": model,
        "adb_keyboard": {
            "installed": package.returncode == 0 and "package:" in (package.stdout or ""),
            "ime_enabled": ADB_KEYBOARD_IME in ime_list,
        },
        "u2_jar": {
            "installed": u2_exists,
            "device_path": U2_DEVICE_PATH,
            "sha256": remote_sha,
        },
    }


def miui_steps() -> list[str]:
    return [
        "保持手机亮屏解锁。",
        "在小米/Redmi/MIUI/HyperOS 的开发者选项开启「USB 调试（安全设置）」和「通过 USB 安装」。",
        "系统要求时完成小米账号、SIM 卡或联网确认，然后重插数据线再试。",
    ]


def install_keyboard(adb: str, serial: str) -> tuple[dict[str, Any], int]:
    assets = verify_assets(["ADBKeyboard.apk"])
    if not assets["ok"]:
        return {"ok": False, "error": "asset_verification_failed", **assets}, 1
    apk = ASSETS_DIR / "ADBKeyboard.apk"
    install = run_adb(adb, ["install", "-r", str(apk)], serial=serial, timeout=120)
    install_output = combined_output(install)
    if install.returncode != 0 and "INSTALL_FAILED_ALREADY_EXISTS" not in install_output:
        if "INSTALL_FAILED_USER_RESTRICTED" in install_output:
            return {
                "ok": False,
                "serial": serial,
                "error": "adb_keyboard_install_blocked",
                "requires_user_action": True,
                "next_steps": miui_steps(),
            }, 2
        return {
            "ok": False,
            "serial": serial,
            "error": "adb_keyboard_install_failed",
            "detail": install_output[:400],
        }, 1

    package_enable = run_adb(
        adb,
        ["shell", "pm", "enable", ADB_KEYBOARD_PACKAGE],
        serial=serial,
    )
    ime_enable = run_adb(
        adb,
        ["shell", "ime", "enable", ADB_KEYBOARD_IME],
        serial=serial,
    )
    status = component_status(adb, serial)
    ok = bool(status["adb_keyboard"]["installed"])
    next_steps: list[str] = []
    if ok and not status["adb_keyboard"]["ime_enabled"]:
        next_steps.append("打开手机“语言与输入法/管理键盘”，手动启用 ADB Keyboard。")
    return {
        "ok": ok,
        "serial": serial,
        "installed": status["adb_keyboard"]["installed"],
        "ime_enabled": status["adb_keyboard"]["ime_enabled"],
        "package_enable": combined_output(package_enable)[:200],
        "ime_enable": combined_output(ime_enable)[:200],
        "next_steps": next_steps,
    }, 0 if ok else 1


def push_u2(adb: str, serial: str) -> tuple[dict[str, Any], int]:
    assets = verify_assets(["u2.jar"])
    if not assets["ok"]:
        return {"ok": False, "error": "asset_verification_failed", **assets}, 1
    jar = ASSETS_DIR / "u2.jar"
    pushed = run_adb(
        adb,
        ["push", str(jar), U2_DEVICE_PATH],
        serial=serial,
        timeout=120,
    )
    if pushed.returncode != 0:
        return {
            "ok": False,
            "serial": serial,
            "error": "u2_push_failed",
            "detail": combined_output(pushed)[:400],
        }, 1
    run_adb(adb, ["shell", "chmod", "644", U2_DEVICE_PATH], serial=serial)
    status = component_status(adb, serial)
    remote_sha = str(status["u2_jar"].get("sha256") or "")
    expected_sha = str(load_manifest()["assets"]["u2.jar"]["sha256"])
    verified = bool(status["u2_jar"]["installed"] and (not remote_sha or remote_sha == expected_sha))
    return {
        "ok": verified,
        "serial": serial,
        "device_path": U2_DEVICE_PATH,
        "sha256": remote_sha,
        "expected_sha256": expected_sha,
        "next_steps": ["回到工蜂应用点击“重新自检”。"] if verified else [],
    }, 0 if verified else 1


def open_settings(adb: str, serial: str, page: str) -> tuple[dict[str, Any], int]:
    action = (
        "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
        if page == "developer"
        else "android.settings.INPUT_METHOD_SETTINGS"
    )
    result = run_adb(adb, ["shell", "am", "start", "-a", action], serial=serial)
    return {
        "ok": result.returncode == 0,
        "serial": serial,
        "page": page,
        "detail": combined_output(result)[:300],
    }, 0 if result.returncode == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="WorkerBee phone component fallback")
    parser.add_argument("--adb", default="", help="path to adb or adb.exe")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("assets", help="verify bundled third-party assets without touching a phone")
    for name in ("status", "install-keyboard", "push-u2"):
        item = sub.add_parser(name)
        item.add_argument("--serial", default="")
        if name != "status":
            item.add_argument("--yes", action="store_true", help="confirm this phone mutation")
    settings = sub.add_parser("open-settings")
    settings.add_argument("--serial", default="")
    settings.add_argument("--page", choices=("developer", "keyboard"), required=True)
    settings.add_argument("--yes", action="store_true", help="confirm opening settings on the phone")
    args = parser.parse_args()

    if args.command == "assets":
        result = verify_assets()
        print_json(result)
        return 0 if result["ok"] else 1

    try:
        adb = find_adb(args.adb)
        if not adb:
            raise RuntimeError("找不到 adb；请启动工蜂或用 --adb 指定安装包内的 adb")
        serial = resolve_serial(adb, args.serial)
        if args.command == "status":
            print_json({"adb": adb, **component_status(adb, serial)})
            return 0
        if not args.yes:
            print_json({
                "ok": False,
                "error": "confirmation_required",
                "next_steps": ["向用户说明将要修改的手机组件，取得同意后加 --yes 重试。"],
            })
            return 2
        if args.command == "install-keyboard":
            payload, code = install_keyboard(adb, serial)
        elif args.command == "push-u2":
            payload, code = push_u2(adb, serial)
        else:
            payload, code = open_settings(adb, serial, args.page)
        payload.setdefault("adb", adb)
        print_json(payload)
        return code
    except Exception as exc:
        print_json({"ok": False, "error": f"{type(exc).__name__}: {str(exc)}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
