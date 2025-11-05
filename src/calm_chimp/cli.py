from __future__ import annotations

import argparse
import logging

from .bootstrap import configure_logging
from .services.http import run_local_server
from .services.mcp import run_mcp_server
from .ui.app import run_gui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calm Chimp command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("gui", help="Launch the desktop GUI.")

    api_parser = subparsers.add_parser("api", help="Start the FastAPI server exposing deterministic tools.")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    mcp_parser = subparsers.add_parser("mcp", help="Start the FastMCP server for LangGraph clients.")
    mcp_parser.add_argument("--host", default="127.0.0.1")
    mcp_parser.add_argument("--port", type=int, default=8765)

    return parser


def main() -> None:
    configure_logging()
    logging.getLogger(__name__).info("Calm Chimp CLI starting")
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "gui":
        run_gui()
    elif args.command == "api":
        run_local_server(host=args.host, port=args.port)
    elif args.command == "mcp":
        run_mcp_server(host=args.host, port=args.port)
    else:  # pragma: no cover - argparse enforces choices
        parser.print_help()


if __name__ == "__main__":
    main()
