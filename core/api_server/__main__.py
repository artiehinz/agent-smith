"""Command entry point for the local dashboard shim."""

from __future__ import annotations

from tools.run_policy_dashboard import run_server


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
