#!/usr/bin/env python3
"""Minimal CLI for interacting with the Alert Engine REST API.

Usage examples:

- Submit an alert:
  poetry run python scripts/alert_cli.py submit \
    --alert-id manual_1 --source manual --severity warning \
    --message "Manual test alert" --corr-id test-123

- Acknowledge an alert:
  poetry run python scripts/alert_cli.py ack --alert-id temp_high:temperature --actor user@example.com

- Clear an alert:
  poetry run python scripts/alert_cli.py clear --alert-id temp_high:temperature

- List active alerts:
  poetry run python scripts/alert_cli.py active

- List configured rules:
  poetry run python scripts/alert_cli.py rules
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, data: dict | None = None) -> tuple[int, dict | list | str]:
    payload = None
    headers = {"Content-Type": "application/json"}
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, e.reason
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert Engine CLI")
    parser.add_argument("command", choices=["submit", "ack", "clear", "active", "rules"], help="Action")
    parser.add_argument("--host", default="http://localhost:5003", help="Base URL of alert API")

    # Submit args
    parser.add_argument("--alert-id")
    parser.add_argument("--source")
    parser.add_argument("--severity", choices=["info", "warning", "critical"]) \
        
    parser.add_argument("--message")
    parser.add_argument("--corr-id", dest="correlation_id")
    parser.add_argument("--persistence", type=int, default=1)
    parser.add_argument("--cooldown", type=int, default=300)
    parser.add_argument("--payload", help="JSON string with extra fields", default="{}")

    # Ack/Clear args
    parser.add_argument("--actor", help="Actor identifier for ack")

    args = parser.parse_args()

    base = args.host.rstrip("/")

    if args.command == "submit":
        if not all([args.alert_id, args.source, args.severity, args.message, args.correlation_id]):
            print("Missing one of --alert-id, --source, --severity, --message, --corr-id", file=sys.stderr)
            return 2
        try:
            extra = json.loads(args.payload)
            if not isinstance(extra, dict):
                raise ValueError
        except Exception:
            print("--payload must be a JSON object", file=sys.stderr)
            return 2
        body = {
            "alert_id": args.alert_id,
            "source": args.source,
            "severity": args.severity,
            "message": args.message,
            "correlation_id": args.correlation_id,
            "persistence_count": args.persistence,
            "cooldown_seconds": args.cooldown,
            "payload": extra,
        }
        status, resp = _request("POST", f"{base}/alerts/submit", body)
        print(status, json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if status and status < 400 else 1

    if args.command == "ack":
        if not args.alert_id or not args.actor:
            print("--alert-id and --actor are required for ack", file=sys.stderr)
            return 2
        status, resp = _request("POST", f"{base}/alerts/{args.alert_id}/acknowledge", {"actor": args.actor})
        print(status, json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if status and status < 400 else 1

    if args.command == "clear":
        if not args.alert_id:
            print("--alert-id is required for clear", file=sys.stderr)
            return 2
        status, resp = _request("POST", f"{base}/alerts/{args.alert_id}/clear")
        print(status, json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if status and status < 400 else 1

    if args.command == "active":
        status, resp = _request("GET", f"{base}/alerts/active")
        print(status, json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if status and status < 400 else 1

    if args.command == "rules":
        status, resp = _request("GET", f"{base}/alert-rules")
        print(status, json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if status and status < 400 else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

