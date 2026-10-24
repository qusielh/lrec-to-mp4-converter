"""L2M command-line converter.

Usage:
    python l2m_cli.py input.lrec output.mp4
"""

from __future__ import annotations

import sys

import l2m_engine as engine


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python l2m_cli.py input.lrec output.mp4", file=sys.stderr)
        return 2
    try:
        engine.convert_one(
            argv[1],
            argv[2],
            lambda line: print(line, flush=True),
            lambda: False,
            lambda frac, remaining: None,
        )
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
