"""
conda subchannel subcommand for CLI
"""

from __future__ import annotations

import argparse
from logging import getLogger
from datetime import datetime, UTC

from conda.base.context import context
from conda.common.io import Spinner
from conda.base.constants import REPODATA_FN

from .core import _fetch_channel, _reduce_index, _dump_records, _write_to_disk

logger = getLogger(f"conda.{__name__}")


def date_argument(date: str) -> float:
    date = str(date).split("-")
    if len(date) == 1 and len(date[0]) > 4:  # timestamp; avoid 4-digit ones (usually a year)
        return datetime.fromtimestamp(float(date[0]), UTC).timestamp()
    if len(date) == 1:
        date.extend(["1", "1"])
    elif len(date) == 2:
        date.append("1")
    if 3 <= len(date) <= 6:  # YYYY-[MM[-DD[-HH[-MM[-SS]]]]]
        return datetime(*[int(x) for x in date], tzinfo=UTC).timestamp()
    raise OSError(f"Wrong date {date}. Needs timestamp or YYYY-[MM[-DD[-HH[-MM[-SS]]]]]")


def configure_parser(parser: argparse.ArgumentParser):
    parser.add_argument("-c", "--channel", required=True, dest="channel")
    parser.add_argument("--repodata-fn", default=REPODATA_FN)
    parser.add_argument("--output", default="subchannel", metavar="PATH")
    parser.add_argument("--subdir", "--platform", dest="subdirs", action="append")
    parser.add_argument(
        "--after",
        metavar="TIME",
        help="Unix timestamp, YYYY-MM-DD or YYYY-MM-DD-HH-MM-SS",
        type=date_argument,
    )
    parser.add_argument(
        "--before",
        metavar="TIME",
        help="Unix timestamp, YYYY-MM-DD or YYYY-MM-DD-HH-MM-SS",
        type=date_argument,
    )
    parser.add_argument("--keep-tree", metavar="SPEC", action="append")
    parser.add_argument("--keep", metavar="SPEC", action="append")
    parser.add_argument("--remove", metavar="SPEC", action="append")


def execute(args: argparse.Namespace) -> int:
    with Spinner("Syncing source channel"):
        subdir_datas = _fetch_channel(
            args.channel, args.subdirs or context.subdirs, args.repodata_fn
        )
    for sd in sorted(subdir_datas, key=lambda sd: sd.channel.name):
        print(" -", sd.channel.name, sd.channel.subdir)

    with Spinner("Filtering package records"):
        records = _reduce_index(
            subdir_datas=subdir_datas,
            specs_to_keep=args.keep,
            specs_to_remove=args.remove,
            trees_to_keep=args.keep_tree,
            after=args.after,
            before=args.before,
        )
    total_count = sum(len(sd._package_records) for sd in subdir_datas)
    filtered_count = len(records)
    if total_count == filtered_count:
        print (" - Didn't filter any records!")
        return 1
    print(" - Reduced from", total_count, "to", filtered_count, "records")

    with Spinner(f"Writing output to {args.output}"):
        repodatas = _dump_records(records, args.channel)
        _write_to_disk(repodatas, args.output)

    return 0
