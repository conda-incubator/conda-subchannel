"""
conda subchannel subcommand for CLI
"""

from __future__ import annotations

import argparse
from logging import getLogger

from conda.base.context import context
from conda.common.io import Spinner
from conda.base.constants import REPODATA_FN

from .core import _fetch_channel, _reduce_index, _dump_records, _write_to_disk

logger = getLogger(f"conda.{__name__}")


def configure_parser(parser: argparse.ArgumentParser):
    parser.add_argument("-c", "--channel", required=True, dest="channel")
    parser.add_argument("--repodata-fn", default=REPODATA_FN)
    parser.add_argument("--output", default="subchannel", metavar="PATH")
    parser.add_argument("--subdir", "--platform", dest="subdirs", action="append")
    parser.add_argument("--after", metavar="TIME")
    parser.add_argument("--before", metavar="TIME")
    parser.add_argument("--keep-tree", metavar="SPEC", action="append")
    parser.add_argument("--remove-tree", metavar="SPEC", action="append")
    parser.add_argument("--keep", metavar="SPEC", action="append")
    parser.add_argument("--remove", metavar="SPEC", action="append")


def execute(args: argparse.Namespace) -> int:
    with Spinner("Syncing source channels"):
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
            trees_to_remove=args.remove_tree,
            after=args.after,
            before=args.before,
        )
    print(" - Reduced to", len(records), "records")

    with Spinner(f"Writing output to {args.output}"):
        repodatas = _dump_records(records, args.channel)
        _write_to_disk(repodatas, args.output)

    return 0
