"""
conda subchannel subcommand for CLI
"""

from __future__ import annotations

import argparse
from logging import getLogger
from datetime import datetime, timezone

from conda.exceptions import ArgumentError
from conda.base.context import context
from conda.common.io import Spinner
from conda.base.constants import REPODATA_FN

from .core import _fetch_channel, _reduce_index, _dump_records, _write_to_disk

logger = getLogger(f"conda.{__name__}")


def date_argument(date: str) -> float:
    date = str(date).split("-")
    if len(date) == 1 and date[0].startswith("ts:"):
        return datetime.fromtimestamp(float(date[0][3:]), timezone.utc).timestamp()
    if len(date) == 1:
        date.extend(["1", "1"])
    elif len(date) == 2:
        date.append("1")
    if 3 <= len(date) <= 6:  # YYYY-[MM[-DD[-HH[-MM[-SS]]]]]
        return datetime(*[int(x) for x in date], tzinfo=timezone.utc).timestamp()
    raise ValueError(
        f"Wrong date {date}. "
        "Needs timestamp as ts:<float> or date as YYYY-[MM[-DD[-HH[-MM[-SS]]]]]"
    )


def configure_parser(parser: argparse.ArgumentParser):
    parser.add_argument("-c", "--channel", required=True, dest="channel")
    parser.add_argument(
        "--repodata-fn",
        default=REPODATA_FN,
        help="Source repodata file to process from channel.",
    )
    parser.add_argument(
        "--output",
        default="subchannel",
        metavar="PATH",
        help="Directory where the subchannel repodata.json artifacts will be written to.",
    )
    parser.add_argument(
        "--subdir",
        "--platform",
        dest="subdirs",
        metavar="PLATFORM",
        action="append",
        help=f"Process records for this platform. Defaults to {context.subdir}. "
        "noarch is always included. Can be used several times.",
    )
    parser.add_argument(
        "--after",
        metavar="TIME",
        help="Timestamp as ts:<float> or date as YYYY-[MM[-DD[-HH[-MM[-SS]]]]]",
        type=date_argument,
    )
    parser.add_argument(
        "--before",
        metavar="TIME",
        help="Timestamp as ts:<float> or date as YYYY-[MM[-DD[-HH[-MM[-SS]]]]]",
        type=date_argument,
    )
    parser.add_argument(
        "--keep-tree",
        metavar="SPEC",
        action="append",
        help="Keep packages matching this spec and their dependencies. Can be used several times.",
    )
    parser.add_argument(
        "--keep",
        metavar="SPEC",
        action="append",
        help="Keep packages matching this spec only. Can be used several times.",
    )
    parser.add_argument(
        "--remove",
        metavar="SPEC",
        action="append",
        help="Remove packages matching this spec. Can be used several times.",
    )


def execute(args: argparse.Namespace) -> int:
    if not any([args.after, args.before, args.keep, args.remove, args.keep_tree]):
        raise ArgumentError("Please provide at least one filter.")

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
        print(" - Didn't filter any records!")
        return 1
    print(" - Reduced from", total_count, "to", filtered_count, "records")

    with Spinner(f"Writing output to {args.output}"):
        repodatas = _dump_records(records, args.channel)
        _write_to_disk(repodatas, args.output)

    return 0
