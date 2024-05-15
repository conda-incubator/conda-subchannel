from __future__ import annotations

import bz2
import hashlib
import json
import logging
from datetime import datetime, timezone
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
        if trees_to_keep:
            specs_from_trees = set()
            for sd, record in _keep_records(subdir_datas, trees_to_keep, after, before):
                if (sd.channel.subdir, record.fn) in records:
                    continue
                records[(sd.channel.subdir, record.fn)] = record
                for dep in record.depends:
                    specs_from_trees.add(MatchSpec(dep))

            # First we filter with the recursive actions
            while specs_from_trees:
                spec = specs_from_trees.pop()
                for sd in subdir_datas:
                    for record in sd.query(spec):
                        if (sd.channel.subdir, record.fn) in records:
                            continue
                        records[(sd.channel.subdir, record.fn)] = record
                        for dep in record.depends:
                            # This step might readd dependencies that are not part of the
                            # requested tree; e.g python=3.9 might add pip, which depends on python,
                            # which will then appear again. We will clear those later.
                            specs_from_trees.add(MatchSpec(dep))

        # Remove records added by circular dependencies (python -> pip -> python); this might
        # break solvability, but in principle the solver should only allow one record per package
        # name in the solution, so it should be ok to remove name matches that are not fitting the
        # initially requested spec. IOW, if a requested spec adds a dependency that ends up
        # depending on the requested spec again, the initial node should satisfy that and doesn't
        # doesn't need the extra ones.
        to_remove = []
        for key, record in records.items():
            if (spec := names_to_keep.get(record.name)) and not spec.match(record):
                to_remove.append(key)
        for key in to_remove:
            del records[key]

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


def _checksum(path, algorithm, buffersize=65536):
    hash_impl = getattr(hashlib, algorithm)()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(buffersize), b""):
            hash_impl.update(block)
    return hash_impl.hexdigest()


def _write_channel_index_md(source_channel: Channel, channel_path: Path):
    channel_path = Path(channel_path)
    lines = [
        f"# {channel_path.name}",
        "",
        f"Derived from [{source_channel.name}]({source_channel.base_url})",
        "",
        ""
    ]
    for subdir in channel_path.glob("*"):
        if subdir.is_file():
            continue
        lines[-1] += f"[{subdir.name}]({subdir.name}) "
    (channel_path / "index.md").write_text("\n".join(lines))


def _write_subdir_index_md(subdir_path: Path):
    subdir_path = Path(subdir_path)
    lines = [
        f"# {'/'.join(subdir_path.parts[-2:])}",
        "| Filename | Size (B) | Last modified | SHA256 | MD5 |",
        "|----------|----------|---------------|--------|-----|",
    ]
    for path in sorted(subdir_path.glob("*")):
        if path.name == "index.md":
            continue
        stat = path.stat()
        size = stat.st_size
        lastmod = datetime.fromtimestamp(stat.st_mtime)
        sha256 = _checksum(path, "sha256")
        md5 = _checksum(path, "md5")
        lines.append(
            f"| [{path.name}]({path.name}) | {size} | {lastmod} | `{sha256}` | `{md5}` |"
        )
    lines.append("")
    lines.append(f"> Last modified on {datetime.now(tz=timezone.utc)}")
    (subdir_path / "index.md").write_text("\n".join(lines))


def _write_to_disk(
    source_channel: Channel | str,
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
        _write_subdir_index_md(path / subdir)

    # noarch must always be present
    noarch_repodata = path / "noarch" / "repodata.json"
    if not noarch_repodata.is_file():
        noarch_repodata.parent.mkdir(parents=True, exist_ok=True)
        noarch_repodata.write_text("{}")
        _write_subdir_index_md(path / "noarch")

    _write_channel_index_md(Channel(source_channel), path)
