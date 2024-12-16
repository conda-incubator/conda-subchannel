from __future__ import annotations

import os
import bz2
import hashlib
import json
import logging
import fnmatch as _fnmatch
import re
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import jinja2
import zstandard
from conda.base.context import context
from conda.common.io import ThreadLimitedThreadPoolExecutor
from conda.base.constants import REPODATA_FN
from conda.core.subdir_data import SubdirData
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.version import VersionOrder

if TYPE_CHECKING:
    import os
    from typing import Any, Iterable, Iterator

    from conda.models.match_spec import MatchSpec
    from conda.models.records import PackageRecord

ZSTD_COMPRESS_LEVEL = 16
ZSTD_COMPRESS_THREADS = -1  # automatic

log = logging.getLogger(f"conda.{__name__}")


# Copied from https://github.com/conda-forge/conda-forge-repodata-patches-feedstock/blob/2daa1f620d750a16849d9bfe340885ac1ad39dc5/recipe/patch_yaml_utils.py#L47C1-L78C35
@lru_cache(maxsize=32768)
def fnmatch(name, pat):
    """Test whether FILENAME matches PATTERN with custom
    allowed optional space via '?( *)'.

    This is useful to match single names with or without a version
    but not other packages.

    Here are various cases to illustrate how this works:

      - 'numpy*' will match 'numpy', 'numpy >=1', and 'numpy-blah >=10'.
      - 'numpy?( *)' will match only 'numpy', 'numpy >=1'.
      - 'numpy' only matches 'numpy'

    **doc string below is from python stdlib**

    Patterns are Unix shell style:

    *       matches everything
    ?       matches any single character
    [seq]   matches any character in seq
    [!seq]  matches any char not in seq

    An initial period in FILENAME is not special.
    Both FILENAME and PATTERN are first case-normalized
    if the operating system requires it.
    If you don't want this, use fnmatchcase(FILENAME, PATTERN).
    """
    name = os.path.normcase(name)
    pat = os.path.normcase(pat)
    match = _fnmatch_build_re(pat)
    return match(name) is not None


@lru_cache(maxsize=32768)
def _fnmatch_build_re(pat):
    repat = "(?s:\\ .*)?".join([_fnmatch.translate(p)[:-2] for p in pat.split("?( *)")]) + "\\Z"
    return re.compile(repat).match


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
    specs_depends_to_remove: Iterable[str] | None = None,
    specs_to_prune: Iterable[str | MatchSpec] | None = None,
    trees_to_keep: Iterable[str | MatchSpec] | None = None,
    after: int | None = None,
    before: int | None = None,
) -> dict[tuple[str, str], PackageRecord]:
    specs_to_keep = [MatchSpec(spec) for spec in (specs_to_keep or ())]
    specs_to_remove = [MatchSpec(spec) for spec in (specs_to_remove or ())]
    specs_depends_to_remove = specs_depends_to_remove or ()
    specs_to_prune = [MatchSpec(spec) for spec in (specs_to_prune or ())]
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

    # Of the packages that survived the keeping, we will remove the ones that do not match the
    # prune filter
    for spec in specs_to_prune:
        for key, record in records.items():
            if spec.name != record.name:
                continue  # ignore if the name doesn't match
            if not spec.match(record):
                to_remove.add(key)

    # These are the explicit removals; if you match this, you are out
    for spec in specs_to_remove:
        for key, record in records.items():
            if spec.match(record):
                to_remove.add(key)

    for spec in specs_depends_to_remove:
        for key, record in records.items():
            for dep in record["depends"]:
                if fnmatch(dep, spec):
                    to_remove.add(key)
                    break

    for key in to_remove:
        records.pop(key)

    return records


def _dump_records(
    records: dict[tuple[str, str], PackageRecord], base_url: str
) -> dict[str, dict[str, Any]]:
    repodatas = {}
    record_keys = (
        "build",
        "build_number",
        "constrains",
        "depends",
        "license",
        "md5",
        "name",
        "sha256",
        "size",
        "subdir",
        "timestamp",
        "version",
    )
    for (subdir, filename), record in records.items():
        if subdir not in repodatas:
            repodatas[subdir] = {
                "repodata_version": 2,
                "info": {
                    "base_url": base_url,
                    "subdir": subdir,
                },
                "packages": {},
                "packages.conda": {},
                "removed": [],
            }
        key = "packages.conda" if record.fn.endswith(".conda") else "packages"
        dumped = record.dump()
        repodatas[record.subdir][key][filename] = {
            key: dumped[key] for key in record_keys if key in dumped
        }
    return repodatas


def _checksum(path, algorithm, buffersize=65536):
    hash_impl = getattr(hashlib, algorithm)()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(buffersize), b""):
            hash_impl.update(block)
    return hash_impl.hexdigest()


def _write_channel_index_html(
    source_channel: Channel,
    channel_path: Path,
    cli_flags: dict[str, Any],
    served_at: str | None = None,
):
    templates_dir = Path(__file__).parent / "templates"
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))
    template = environment.get_template("channel.j2.html")
    channel_path = Path(channel_path)
    content = template.render(
        subchannel_name=channel_path.name,
        source_channel_url=source_channel.base_url,
        source_channel_name=source_channel.name,
        subdirs=[path.name for path in channel_path.glob("*") if path.is_dir()],
        cli_flags=cli_flags,
        subchannel_url=served_at or "",
    )
    (channel_path / "index.html").write_text(content)
    (channel_path / "style.css").write_text((templates_dir / "style.css").read_text())


def _write_subdir_index_html(subdir_path: Path, served_at: str | None = None):
    templates_dir = Path(__file__).parent / "templates"
    environment = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))
    template = environment.get_template("subdir.j2.html")
    repodatas = []
    packages = []
    base_url = None
    for path in sorted(subdir_path.glob("*")):
        if path.name in ("index.md", "index.html"):
            continue
        stat = path.stat()
        url = "/".join([served_at, subdir_path.name, path.name]) if served_at else path.name
        repodatas.append(
            {
                "filename": path.name,
                "url": url,
                "size": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "sha256": _checksum(path, "sha256"),
                "md5": _checksum(path, "md5"),
            }
        )
        if path.name == "repodata.json":
            repodata = json.loads(path.read_text())
            if repodata:
                base_url = repodata["info"]["base_url"]
                for key in ("packages", "packages.conda"):
                    for filename in repodata.get(key, ()):
                        packages.append(filename)

    packages.sort(key=_sortkey_package_filenames)
    content = template.render(
        subchannel_name=subdir_path.parent.name,
        subchannel_url="../",
        subdir=subdir_path.name,
        repodatas=repodatas,
        last_modified=datetime.now(tz=timezone.utc),
        base_url=base_url,
        packages=packages,
    )
    (subdir_path / "index.html").write_text(content)


def _write_to_disk(
    source_channel: Channel | str,
    repodatas: dict[str, dict[str, Any]],
    path: os.PathLike | str,
    cli_flags: dict[str, Any],
    served_at: str | None = None,
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
        _write_subdir_index_html(path / subdir, served_at)

    # noarch must always be present
    noarch_repodata = path / "noarch" / "repodata.json"
    if not noarch_repodata.is_file():
        noarch_repodata.parent.mkdir(parents=True, exist_ok=True)
        noarch_repodata.write_text("{}")
        _write_subdir_index_html(path / "noarch", served_at)

    _write_channel_index_html(Channel(source_channel), path, cli_flags, served_at)


def _sortkey_package_filenames(fn: str):
    basename, ext = os.path.splitext(fn)
    name, version, build = basename.rsplit("-", 2)
    build_number = build
    if "_" in build:
        for field in build.split("_"):
            if field.isdigit():
                build_number = field
                break
    return name, VersionOrder(version), build_number, ext
