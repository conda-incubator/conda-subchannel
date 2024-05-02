from __future__ import annotations

import bz2
import json
from pathlib import Path
from typing import TYPE_CHECKING

from conda.base.context import context
from conda.common.io import ThreadLimitedThreadPoolExecutor
from conda.base.constants import REPODATA_FN
from conda.core.subdir_data import SubdirData
from conda.models.channel import Channel

if TYPE_CHECKING:
    import os
    from typing import Any, Iterable

    from conda.models.match_spec import MatchSpec
    from conda.models.records import PackageRecord


def _fetch_channel(channel, subdirs=None, repodata_fn=REPODATA_FN):
    def fetch(url):
        subdir_data = SubdirData(Channel(url), repodata_fn=repodata_fn)
        subdir_data.load()
        return subdir_data

    with ThreadLimitedThreadPoolExecutor(max_workers=context.fetch_threads) as executor:
        urls = Channel(channel).urls(with_credentials=True, subdirs=subdirs)
        return list(executor.map(fetch, urls))


def _reduce_index(
    subdir_datas: Iterable[SubdirData],
    specs_to_keep: Iterable[str | MatchSpec] | None = None,
    specs_to_remove: Iterable[str | MatchSpec] | None = None,
    trees_to_keep: Iterable[str | MatchSpec] | None = None,  # TODO
    trees_to_remove: Iterable[str | MatchSpec] | None = None,  # TODO
    after: int | str | None = None,  # TODO
    before: int | str | None = None,  # TODO
) -> dict[tuple[str, str], PackageRecord]:
    counts = []
    records = {
        (sd.channel.subdir, rec.fn): rec for sd in subdir_datas for rec in sd.iter_records()
    }
    counts.append(("Initial", len(records)))
    if specs_to_keep:
        records = {
            (sd.channel.subdir, rec.fn): rec
            for spec in specs_to_keep
            for sd in subdir_datas
            for rec in sd.query(spec)
        }
        counts.append(("After Keep", len(records)))
    if specs_to_remove:
        for spec in specs_to_remove:
            for sd in subdir_datas:
                for rec in sd.query(spec):
                    records.pop((sd.channel.subdir, rec.fn), None)
        counts.append(("After Remove", len(records)))
    return records


def _dump_records(
    records: dict[tuple[str, str], PackageRecord], source_channel: Channel | str
) -> dict[str, dict[str, Any]]:
    source_channel = Channel(source_channel)
    repodatas = {}
    for (subdir, filename), record in records.items():
        if subdir not in repodatas:
            repodatas[subdir] = {
                "metadata": {
                    "repodata_version": 2,
                    "base_url": source_channel.base_url,
                    "subdir": subdir,
                },
                "packages": {},
                "packages.conda": {},
            }
        key = "packages.conda" if record.fn.endswith(".conda") else "packages"
        repodatas[record.subdir][key][filename] = record.dump()  # TODO
    return repodatas


def _write_to_disk(
    repodatas: dict[str, dict[str, Any]],
    path: os.PathLike | str,
    outputs: Iterable[str] = ("bz2", "zstd"),
):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for subdir, repodata in repodatas.items():
        (path / subdir).mkdir(parents=True, exist_ok=True)
        repodata_json = path / subdir / "repodata.json"
        json_contents = json.dumps(repodata, indent=2, sort_keys=True)
        repodata_json.write_text(json_contents)
        if "bz2" in outputs:
            # Create BZ2 compressed
            with open(str(repodata_json) + ".bz2", "wb") as fo:
                fo.write(bz2.compress(json_contents.encode("utf-8")))
        if "zstd" in outputs:
            ...
    # noarch must always be present
    noarch_repodata = path / "noarch" / "repodata.json"
    if not noarch_repodata.is_file():
        noarch_repodata.parent.mkdir(parents=True, exist_ok=True)
        noarch_repodata.write_text("{}")
