from __future__ import annotations

import bz2
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import zstandard
from conda.base.context import context
from conda.common.io import ThreadLimitedThreadPoolExecutor
from conda.base.constants import REPODATA_FN
from conda.core.subdir_data import SubdirData
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec

if TYPE_CHECKING:
    import os
    from typing import Any, Iterable, Iterator

    from conda.models.match_spec import MatchSpec
    from conda.models.records import PackageRecord

ZSTD_COMPRESS_LEVEL = 16
ZSTD_COMPRESS_THREADS = -1  # automatic

log = logging.getLogger(f"conda.{__name__}")


def _fetch_channel(channel, subdirs=None, repodata_fn=REPODATA_FN):
    def fetch(url):
        subdir_data = SubdirData(Channel(url), repodata_fn=repodata_fn)
        subdir_data.load()
        return subdir_data

    with ThreadLimitedThreadPoolExecutor(max_workers=context.fetch_threads) as executor:
        urls = Channel(channel).urls(with_credentials=True, subdirs=subdirs)
        return list(executor.map(fetch, urls))


def _keep_records(
    subdir_datas: Iterable[SubdirData],
    specs: Iterable[MatchSpec],
    after: int | None = None,
    before: int | None = None,
) -> Iterator[tuple[SubdirData, PackageRecord]]:
    if specs:
        for spec in specs:
            for sd in subdir_datas:
                for record in sd.query(spec):
                    if before is not None and record.timestamp >= before:
                        continue
                    if after is not None and record.timestamp <= after:
                        continue
                    yield sd, record
    elif before is not None or after is not None:
        for sd in subdir_datas:
            for record in sd.iter_records():
                if before is not None and record.timestamp >= before:
                    continue
                if after is not None and record.timestamp <= after:
                    continue
                yield sd, record 
    else:
        raise ValueError("Must provide at least one truthy 'specs', 'after' or 'before'.")


def _reduce_index(
    subdir_datas: Iterable[SubdirData],
    specs_to_keep: Iterable[str | MatchSpec] | None = None,
    specs_to_remove: Iterable[str | MatchSpec] | None = None,
    trees_to_keep: Iterable[str | MatchSpec] | None = None,
    after: int | None = None,
    before: int | None = None,
) -> dict[tuple[str, str], PackageRecord]:
    specs_to_keep = [MatchSpec(spec) for spec in (specs_to_keep or ())]
    specs_to_remove = [MatchSpec(spec) for spec in (specs_to_remove or ())]
    trees_to_keep = [MatchSpec(spec) for spec in (trees_to_keep or ())]
    if trees_to_keep or specs_to_keep or after is not None or before is not None:
        records = {}
        names_to_keep = {MatchSpec(spec).name: spec for spec in (*specs_to_keep, *trees_to_keep)}
        names_to_remove = {MatchSpec(spec).name: spec for spec in specs_to_remove}
        if trees_to_keep:
            specs_from_trees = set()
            for sd, record in _keep_records(subdir_datas, trees_to_keep, after, before):
                if (sd.channel.subdir, record.fn) in records:
                    continue
                records[(sd.channel.subdir, record.fn)] = record
                for dep in record.depends:
                    specs_from_trees.add(MatchSpec(dep))

            # First we filter with the recursive actions
            maybe_dep_cycle = set()
            while specs_from_trees:
                spec = specs_from_trees.pop()
                for sd in subdir_datas:
                    for record in sd.query(spec):
                        if (sd.channel.subdir, record.fn) in records:
                            continue
                        records[(sd.channel.subdir, record.fn)] = record
                        for dep in record.depends:
                            dep_spec = MatchSpec(dep)
                            if requested_spec := names_to_keep.get(dep_spec.name):
                                if dep_spec.name not in names_to_remove:
                                    maybe_dep_cycle.add(dep)
                                # This can introduce cycles; let's hope the merged spec works
                                dep_spec = MatchSpec.merge([dep_spec, requested_spec])[0]
                            specs_from_trees.add(dep_spec)
            if maybe_dep_cycle:
                log.warning(
                    "Found potential dependency cycles in your keep-trees. This might mean that "
                    "you ended up with more packages than intended. To filter those out, consider "
                    "adding a --remove flag with the negated --keep-tree. This usually happens "
                    "with --keep=python=x.y and add_pip_as_python_dependency=true. To remediate, "
                    "add --remove=python!=x.y. The problematic specs are: %s",
                    sorted(maybe_dep_cycle)
                )
        if specs_to_keep or after is not None or before is not None:
            # Now we also add the slice of non-recursive keeps:
            for sd, record in _keep_records(subdir_datas, specs_to_keep, after, before):
                if (sd.channel.subdir, record.fn) in records:
                    continue
                records[(sd.channel.subdir, record.fn)] = record
    else:
        # No keep filters = We start with _everything_
        records = {
            (sd.channel.subdir, record.fn): record
            for sd in subdir_datas
            for record in sd.iter_records()
        }

    # Now that we know what to keep, we remove stuff
    to_remove = set()
    for spec in specs_to_remove:
        for key, record in records.items():
            if spec.match(record):
                to_remove.add(key)
    for key in to_remove:
        records.pop(key)

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
        repodatas[record.subdir][key][filename] = record.dump()
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
            # Create compressed BZ2
            with open(str(repodata_json) + ".bz2", "wb") as fo:
                fo.write(bz2.compress(json_contents.encode("utf-8")))
        if "zstd" in outputs:
            # Create compressed ZSTD
            with open(str(repodata_json) + ".zst", "wb") as fo:
                repodata_zst_content = zstandard.ZstdCompressor(
                    level=ZSTD_COMPRESS_LEVEL, threads=ZSTD_COMPRESS_THREADS
                ).compress(json_contents.encode("utf-8"))
                fo.write(repodata_zst_content)
    # noarch must always be present
    noarch_repodata = path / "noarch" / "repodata.json"
    if not noarch_repodata.is_file():
        noarch_repodata.parent.mkdir(parents=True, exist_ok=True)
        noarch_repodata.write_text("{}")
