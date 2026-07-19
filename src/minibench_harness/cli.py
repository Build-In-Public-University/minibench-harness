from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import write_demo_cycle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='MiniBench B2A forecasting harness')
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo-cycle', help='write a demo sealed forecast/settlement cycle')
    demo.add_argument('--out', default='artifacts/demo-cycle')
    args = parser.parse_args(argv)
    if args.command == 'demo-cycle':
        summary = write_demo_cycle(Path(args.out))
        print(json.dumps(summary, sort_keys=True))
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
