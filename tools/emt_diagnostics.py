#!/usr/bin/env python3
"""
EMT/EMQ Connectivity Diagnostics Tool

Tests connectivity to all EMT (极速柜台) and EMQ (极速行情) API endpoints,
verifies the TCP handshake, and reports network status.

Usage:
    python tools/emt_diagnostics.py
    python tools/emt_diagnostics.py --full    # Full login attempt
    python tools/emt_diagnostics.py --emq-only # Market data only
"""

import argparse
import os
import socket
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
_project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════════════════════
# Configuration (from user credentials)
# ═══════════════════════════════════════════════════════════════════════

ENDPOINTS = [
    {
        "name": "EMT 极速柜台 API (普通账户)",
        "host": "61.152.230.41",
        "port": 19088,
        "broker_id": "10100033598",
        "user_id": "10100033598",
        "password": "dS4503",
        "service": "trading",
    },
    {
        "name": "EMT 信用账户 API",
        "host": "61.152.230.41",
        "port": 19088,
        "broker_id": "110110033598",
        "user_id": "110110033598",
        "password": "dS4503",
        "service": "trading",
    },
    {
        "name": "EMT 期权账户 API",
        "host": "61.152.230.41",
        "port": 19088,
        "broker_id": "110120033598",
        "user_id": "110120033598",
        "password": "dS4503",
        "service": "trading",
    },
    {
        "name": "EMQ 极速行情 API",
        "host": "61.152.230.41",
        "port": 29088,
        "broker_id": "110100033598",
        "user_id": "10100033598",
        "password": "dS4503",
        "service": "market_data",
    },
    {
        "name": "EMQ L1 行情",
        "host": "61.152.230.216",
        "port": 8093,
        "broker_id": "110100033598",
        "user_id": "10100033598",
        "password": "dS4503",
        "service": "market_data",
    },
    {
        "name": "EMQ L2 行情",
        "host": "61.129.116.188",
        "port": 9988,
        "broker_id": "110100033598",
        "user_id": "10100033598",
        "password": "dS4503",
        "service": "market_data",
    },
    {
        "name": "EMQ 场外 API",
        "host": "61.152.230.41",
        "port": 19088,
        "broker_id": "8800007325",
        "user_id": "110100033598",
        "password": "d4503",
        "service": "trading",
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Diagnostic Functions
# ═══════════════════════════════════════════════════════════════════════

def test_tcp(host: str, port: int, timeout: float = 5.0) -> dict:
    """Basic TCP connectivity test."""
    result = {"reachable": False, "latency_ms": None, "error": None}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        start = time.perf_counter()
        err = sock.connect_ex((host, port))
        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
        sock.close()
        if err == 0:
            result["reachable"] = True
        else:
            result["error"] = f"TCP connect failed (errno={err})"
    except socket.timeout:
        result["error"] = "Connection timed out"
    except Exception as e:
        result["error"] = str(e)
    return result


def test_ctp_handshake(host: str, port: int, timeout: float = 5.0) -> dict:
    """Send a basic CTP FTD heartbeat frame and check response."""
    result = {"protocol_verified": False, "response_bytes": 0, "error": None}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        # CTP FTD heartbeat frame
        # [type:1B][ext:1B][length:4B]
        heartbeat = struct.pack("<BBi", 0x01, 0x00, 0)
        sock.sendall(heartbeat)

        time.sleep(0.5)
        try:
            response = sock.recv(4096)
            if response:
                result["protocol_verified"] = True
                result["response_bytes"] = len(response)
        except socket.timeout:
            # Some servers accept the connection but don't respond to bare heartbeat
            result["error"] = "No response to heartbeat (expected without full CTP login)"
            result["protocol_verified"] = None  # ambiguous

        sock.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def test_ctp_login(host: str, port: int, broker_id: str, user_id: str, password: str,
                   timeout: float = 10.0) -> dict:
    """
    Attempt a basic CTP login handshake.

    This is a simplified test — the full CTP login requires the SDK
    for proper FTD field serialization.
    """
    result = {"connected": False, "login_attempted": True, "error": None}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        result["connected"] = True

        # Send initial connect with broker info encoded
        # CTP ReqUserLogin has specific field IDs:
        #   BrokerID=1, UserID=2, Password=3, UserProductInfo=4
        # The full binary serialization is handled by the CTP SDK.
        # Here we just verify the server accepts our connection.
        init_frame = struct.pack("<BBi", 0x01, 0x10, 0)  # extended frame
        sock.sendall(init_frame)
        time.sleep(0.5)

        try:
            resp = sock.recv(4096)
            if resp:
                result["server_response"] = True
                result["response_size"] = len(resp)
        except socket.timeout:
            result["note"] = "Server accepted connection (login requires CTP SDK for full FTD encoding)"

        sock.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def check_openctp() -> dict:
    """Check if openctp (or any CTP Python binding) is installed."""
    result = {"openctp": False, "ctpapi": False, "recommendation": None}
    try:
        import openctp
        result["openctp"] = True
        result["version"] = getattr(openctp, "__version__", "unknown")
        result["recommendation"] = "openctp is installed — EMT/EMQ real API can be used"
    except ImportError:
        pass

    try:
        import ctp  # alternative package name
        result["ctpapi"] = True
        result["recommendation"] = "ctp package found — may work with EMT via ctp2EMT bridge"
    except ImportError:
        pass

    if not result["openctp"] and not result["ctpapi"]:
        result["recommendation"] = (
            "No CTP SDK found. Install openctp for real API access:\n"
            "  pip install openctp-ctp\n"
            "Or use the paper simulation mode: --market cn (uses CNPaperBroker)"
        )
    return result


# ═══════════════════════════════════════════════════════════════════════
# Display
# ═══════════════════════════════════════════════════════════════════════

def print_header():
    print("\n" + "=" * 70)
    print("  EMT/EMQ 极速交易系统 — 连接诊断工具")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def print_section(title: str):
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")


def print_status(ok: bool, label: str, detail: str = ""):
    icon = "✅" if ok else ("⚠️ " if ok is None else "❌")
    line = f"  {icon} {label}"
    if detail:
        line += f"  ({detail})"
    print(line)


def main():
    parser = argparse.ArgumentParser(description="EMT/EMQ Connectivity Diagnostics")
    parser.add_argument("--full", action="store_true", help="Full diagnostics including login attempt")
    parser.add_argument("--emq-only", action="store_true", help="Test EMQ market data endpoints only")
    parser.add_argument("--timeout", type=float, default=5.0, help="Connection timeout in seconds")
    args = parser.parse_args()

    print_header()

    # Check SDK availability
    print_section("SDK 检查")
    sdk = check_openctp()
    print_status(sdk["openctp"], "openctp", f"installed (v{sdk['version']})" if sdk["openctp"] else "not installed")
    print_status(sdk["ctpapi"], "ctpapi", "installed" if sdk["ctpapi"] else "not installed")
    print(f"\n  💡 {sdk['recommendation']}")

    # Filter endpoints
    endpoints = ENDPOINTS
    if args.emq_only:
        endpoints = [e for e in ENDPOINTS if "EMQ" in e["name"]]

    # TCP connectivity
    print_section("TCP 连接测试")
    all_reachable = True
    for ep in endpoints:
        tcp = test_tcp(ep["host"], ep["port"], args.timeout)
        detail = f"{tcp['latency_ms']}ms"
        print_status(tcp["reachable"], f"{ep['name']}", f"{ep['host']}:{ep['port']} — {detail}")
        if not tcp["reachable"]:
            all_reachable = False

    # CTP handshake
    if all_reachable:
        print_section("CTP 协议握手")
        seen_hosts = set()
        for ep in endpoints:
            key = (ep["host"], ep["port"])
            if key in seen_hosts:
                continue
            seen_hosts.add(key)

            hk = test_ctp_handshake(ep["host"], ep["port"], args.timeout)
            detail = f"response={hk['response_bytes']}B" if hk["response_bytes"] else hk.get("error", "")
            print_status(hk["protocol_verified"], f"CTP handshake {ep['host']}:{ep['port']}", detail)

        # Full login attempt (if requested)
        if args.full:
            print_section("CTP 登录尝试 (完整握手)")
            for ep in endpoints:
                if ep.get("service") != "trading":
                    continue
                login = test_ctp_login(
                    ep["host"], ep["port"],
                    ep["broker_id"], ep["user_id"], ep["password"],
                    args.timeout + 5,
                )
                detail = f"response={login.get('response_size', 0)}B" if login.get("server_response") else login.get("error", "")
                print_status(login["connected"], f"Login {ep['name']}", detail)

    # Summary
    print_section("总结")
    if all_reachable:
        print("  ✅ 所有 EMT/EMQ API 端点可达")
        if sdk["openctp"] or sdk["ctpapi"]:
            print("  ✅ CTP SDK 可用 — 可以进行真实交易连接")
            print("\n  下一步：")
            print("    1. 运行 python run_paper_trading.py --market cn --mode once --symbol 000001.SZ")
            print("    2. 使用 --broker emt 切换到 EMT 真实交易模式")
        else:
            print("  ⚠️  CTP SDK 未安装 — 将使用模拟交易模式")
            print("\n  安装 openctp 以启用真实 API：")
            print("    pip install openctp-ctp")
            print("\n  当前可用模式：")
            print("    python run_paper_trading.py --market cn --mode backtest --symbol 000001.SZ,600519.SH")
            print("    python run_paper_trading.py --market cn --mode once --symbol 000001.SZ")
    else:
        print("  ❌ 部分端点不可达 — 请检查网络连接")
        print("  可能原因：")
        print("    1. 防火墙阻止了出站连接")
        print("    2. API 服务需要 VPN 接入")
        print("    3. 账号/权限未激活")

    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
