"""Manage the project services inside a reconnectable tmux session."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = Path("logs/tmux")
DEFAULT_SESSION_NAME = "dt-stack"


@dataclass(frozen=True)
class ServiceSpec:
    """Describe one service launched in its own tmux window."""

    window_name: str
    make_target: str
    delay_seconds: int


def build_service_specs() -> list[ServiceSpec]:
    """Return the launch order used on the Raspberry Pi."""

    services = [
        ServiceSpec(window_name="database", make_target="run-database", delay_seconds=30),
        ServiceSpec(window_name="preprocessing", make_target="run-preprocessing", delay_seconds=60),
        ServiceSpec(
            window_name="image-analysis", make_target="run-image-analysis", delay_seconds=15
        ),
        ServiceSpec(window_name="alerts", make_target="run-alert-engine", delay_seconds=15),
        ServiceSpec(window_name="controller", make_target="run-controller", delay_seconds=15),
        ServiceSpec(window_name="dashboard", make_target="run-dashboard", delay_seconds=15),
        ServiceSpec(window_name="collector", make_target="run-collector", delay_seconds=10),
    ]
    return services


def build_window_command(service: ServiceSpec, log_dir: Path = DEFAULT_LOG_DIR) -> str:
    """Return the shell command executed in one tmux window."""

    log_file = log_dir / f"{service.window_name}.log"
    exit_file = log_dir / f"{service.window_name}.exit"
    return (
        "bash -lc '"
        "set -o pipefail; "
        f"mkdir -p {log_dir}; "
        f"rm -f {exit_file}; "
        f"make {service.make_target} 2>&1 | tee -a {log_file}; "
        "status=$?; "
        f"printf '%s\\n' \"$status\" > {exit_file}; "
        'exit "$status"'
        "'"
    )


def session_exists(session_name: str) -> bool:
    """Return whether the tmux session already exists."""

    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def require_tmux() -> None:
    """Fail fast when tmux is not installed."""

    if shutil.which("tmux") is None:
        raise RuntimeError("tmux is not installed or not on PATH")


def run_tmux(args: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    """Run tmux with the repository root as the working directory."""

    return subprocess.run(
        ["tmux", *args],
        check=True,
        cwd=REPO_ROOT,
        capture_output=capture_output,
        text=True,
    )


def start_stack(session_name: str, log_dir: Path) -> int:
    """Start the stack in a detached tmux session."""

    require_tmux()
    if session_exists(session_name):
        print(f"tmux session '{session_name}' already exists", file=sys.stderr)
        return 1

    services = build_service_specs()
    first_service, *remaining_services = services
    run_tmux(
        [
            "new-session",
            "-d",
            "-s",
            session_name,
            "-n",
            first_service.window_name,
            "-c",
            str(REPO_ROOT),
            build_window_command(first_service, log_dir=log_dir),
        ]
    )
    run_tmux(["set-option", "-t", session_name, "remain-on-exit", "on"])

    print("Prerequisite services remain external to tmux: Kafka and PostgreSQL/TimescaleDB.")
    print(f"Started tmux session '{session_name}'.")
    print(f"Logs are written under {REPO_ROOT / log_dir}.")

    for service in services:
        print(f"- {service.window_name}: make {service.make_target}")

    for previous_service, service in zip(services, remaining_services):
        if previous_service.delay_seconds > 0:
            time.sleep(previous_service.delay_seconds)
        run_tmux(
            [
                "new-window",
                "-t",
                session_name,
                "-n",
                service.window_name,
                "-c",
                str(REPO_ROOT),
                build_window_command(service, log_dir=log_dir),
            ]
        )

    print(f"Attach with: tmux attach -t {session_name}")
    return 0


def attach_stack(session_name: str) -> int:
    """Attach to the running tmux session."""

    require_tmux()
    if not session_exists(session_name):
        print(f"tmux session '{session_name}' does not exist", file=sys.stderr)
        return 1

    run_tmux(["attach-session", "-t", session_name])
    return 0


def stop_stack(session_name: str) -> int:
    """Stop the tmux session and all windows in it."""

    require_tmux()
    if not session_exists(session_name):
        print(f"tmux session '{session_name}' does not exist", file=sys.stderr)
        return 1

    run_tmux(["kill-session", "-t", session_name])
    print(f"Stopped tmux session '{session_name}'.")
    return 0


def status_stack(session_name: str, log_dir: Path) -> int:
    """Print a compact status table for the stack windows."""

    require_tmux()
    if not session_exists(session_name):
        print(f"tmux session '{session_name}' is not running")
        return 1

    result = run_tmux(
        [
            "list-windows",
            "-t",
            session_name,
            "-F",
            "#{window_name}\t#{pane_dead}\t#{pane_current_command}",
        ],
        capture_output=True,
    )

    print("service\tstate\texit\tcommand\tlog")
    for line in result.stdout.strip().splitlines():
        window_name, pane_dead, command = line.split("\t")
        exit_file = REPO_ROOT / log_dir / f"{window_name}.exit"
        exit_status = exit_file.read_text(encoding="utf-8").strip() if exit_file.exists() else "-"
        state = "exited" if pane_dead == "1" else "running"
        log_path = REPO_ROOT / log_dir / f"{window_name}.log"
        print(f"{window_name}\t{state}\t{exit_status}\t{command}\t{log_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        description="Launch the project stack inside a reconnectable tmux session."
    )
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start", help="start the stack in a detached tmux session")

    subparsers.add_parser("attach", help="attach to the tmux session")
    subparsers.add_parser("status", help="show tmux window state and log locations")
    subparsers.add_parser("stop", help="stop the tmux session")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the tmux stack CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        return start_stack(session_name=args.session_name, log_dir=args.log_dir)
    if args.command == "attach":
        return attach_stack(session_name=args.session_name)
    if args.command == "status":
        return status_stack(session_name=args.session_name, log_dir=args.log_dir)
    if args.command == "stop":
        return stop_stack(session_name=args.session_name)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
