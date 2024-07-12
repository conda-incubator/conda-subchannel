"""
conda subchannel subcommand for CLI
"""

from __future__ import annotations

import argparse
from logging import getLogger
from datetime import datetime, timezone

from conda.exceptions import ArgumentError
from conda.base.constants import REPODATA_FN
from conda.base.context import context
from conda.common.io import Spinner
from conda.models.channel import Channel

from .core import _fetch_channel, _reduce_index, _dump_records, _write_to_disk

log = getLogger(f"conda.{__name__}")


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
    parser.add_argument(
        "-c",
        "--channel",
        required=True,
        dest="channel",
        help="Source conda channel.",
    )
    parser.add_argument(
        "--repodata-fn",
        default=REPODATA_FN,
        help="Source repodata file to process from channel.",
    )
    parser.add_argument(
        "--base-url",
        required=False,
        help="URL where the packages will be available. "
        "Defaults to the base URL for '--channel'. Only needed if the user wants to mirror "
        "the required packages separately.",
    )
    parser.add_argument(
        "--output",
        default="subchannel",
        metavar="PATH",
        help="Directory where the subchannel repodata.json artifacts will be written to.",
    )
    parser.add_argument(
        "--served-at",
        metavar="URL",
        help="URL or location where the subchannel files will be eventually served. "
        "Used for the HTML output.",
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
        "--prune",
        metavar="SPEC",
        action="append",
        help="Remove the distributions of this package name that do not match this spec.",
    )
    parser.add_argument(
        "--remove",
        metavar="SPEC",
        action="append",
        help="Remove packages matching this spec. Can be used several times.",
    )


def execute(args: argparse.Namespace) -> int:
    if not any([args.after, args.before, args.keep, args.remove, args.keep_tree, args.prune]):
        raise ArgumentError("Please provide at least one filter.")

    with Spinner("Syncing source channel"):
        subdirs = args.subdirs or context.subdirs
        if "noarch" not in subdirs:
            subdirs = *subdirs, "noarch"
        subdir_datas = _fetch_channel(args.channel, subdirs, args.repodata_fn)
    for sd in sorted(subdir_datas, key=lambda sd: sd.channel.name):
        print(" -", sd.channel.name, sd.channel.subdir)

    kwargs = {
        "subdir_datas": subdir_datas,
        "specs_to_keep": args.keep,
        "specs_to_remove": args.remove,
        "specs_to_prune": args.prune,
        "trees_to_keep": args.keep_tree,
        "after": args.after,
        "before": args.before,
    }
    with Spinner("Filtering package records"):
        records = _reduce_index(**kwargs)
    total_count = sum(len(sd._package_records) for sd in subdir_datas)
    filtered_count = len(records)
    if total_count == filtered_count:
        print(" - Didn't filter any records!")
        return 1
    print(" - Reduced from", total_count, "to", filtered_count, "records")

    with Spinner(f"Writing output to {args.output}"):
        base_url = args.base_url or Channel(args.channel).base_url
        repodatas = _dump_records(records, base_url)
        kwargs.pop("subdir_datas")
        _write_to_disk(
            args.channel,
            repodatas,
            args.output,
            cli_flags=kwargs,
            served_at=args.served_at,
        )

    return 0
