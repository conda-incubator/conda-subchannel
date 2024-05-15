import sys
from datetime import datetime, timezone

import pytest
from conda.base.context import context
from conda.core.subdir_data import SubdirData
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.exceptions import ArgumentError, DryRunExit, PackagesNotFoundError
from conda.testing import conda_cli  # noqa


def test_noop(conda_cli):
    with pytest.raises(ArgumentError, match="Please provide at least one filter."):
        out, err, rc = conda_cli("subchannel", "-c", "conda-forge")


def test_noop_star(conda_cli):
    out, err, rc = conda_cli("subchannel", "-c", "conda-forge", "--keep", "*")
    assert rc == 1
    assert "Didn't filter any records" in out


def test_only_python(conda_cli, tmp_path):
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--keep",
        "python",
        "--output",
        tmp_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    for subdir in context.subdir, "noarch":
        if (tmp_path / subdir / "repodata.json").is_file():
            tested += 1
            channel = Channel(str(tmp_path / subdir))
            sd = SubdirData(channel)
            sd.load()
            assert all(rec.name == "python" for rec in sd.iter_records())
    assert tested


def test_python_tree(conda_cli, tmp_path, monkeypatch):
    spec = "python=3.9"
    channel_path = tmp_path / "channel"
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--keep-tree",
        spec,
        "--output",
        channel_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    tested += 1
    channel = Channel(str(channel_path / context.subdir))
    sd = SubdirData(channel)
    sd.load()
    python_count = 0
    other_count = 0
    py39 = MatchSpec(spec)
    for record in sd.iter_records():  # we should see Python and their dependencies
        if record.name == "python":
            assert py39.match(record)
            python_count += 1
        else:
            other_count += 1
    assert python_count
    assert other_count

    monkeypatch.setenv("CONDA_PKGS_DIRS", str(tmp_path / "pkgs"))
    # This should be solvable
    with pytest.raises(DryRunExit):
        conda_cli(
            "create",
            "--dry-run",
            "-n",
            "unused",
            "--override-channels",
            "--channel",
            channel_path,
            "python=3.9",
        )

    # This should be unsolvable, we didn't take Python 3.10 in the subchannel
    with pytest.raises(PackagesNotFoundError):
        conda_cli(
            "create",
            "--dry-run",
            "-n",
            "unused",
            "--override-channels",
            "--channel",
            channel_path,
            "python=3.10",
        )


def test_not_python(conda_cli, tmp_path):
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--remove",
        "python",
        "--output",
        tmp_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    for subdir in context.subdir, "noarch":
        if (tmp_path / subdir / "repodata.json").is_file():
            tested += 1
            channel = Channel(str(tmp_path / subdir))
            sd = SubdirData(channel)
            sd.load()
            assert not [rec for rec in sd.iter_records() if rec.name == "python"]
    assert tested


def test_only_after(conda_cli, tmp_path):
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--after",
        "2024",
        "--output",
        tmp_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    timestamp_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    for subdir in context.subdir, "noarch":
        if (tmp_path / subdir / "repodata.json").is_file():
            tested += 1
            channel = Channel(str(tmp_path / subdir))
            sd = SubdirData(channel)
            sd.load()
            assert all(rec.timestamp >= timestamp_2024 for rec in sd.iter_records())
    assert tested


def test_only_before(conda_cli, tmp_path):
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--before",
        "2017",
        "--platform",
        "osx-64",
        "--output",
        tmp_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    timestamp_2024 = datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp()
    for subdir in context.subdir, "noarch":
        if (tmp_path / subdir / "repodata.json").is_file():
            tested += 1
            channel = Channel(str(tmp_path / subdir))
            sd = SubdirData(channel)
            sd.load()
            assert all(rec.timestamp <= timestamp_2024 for rec in sd.iter_records())
    assert tested


def test_between_dates(conda_cli, tmp_path):
    out, err, rc = conda_cli(
        "subchannel",
        "-c",
        "conda-forge",
        "--after",
        "2023",
        "--before",
        "2024",
        "--platform",
        "linux-64",
        "--output",
        tmp_path,
    )
    print(out)
    print(err, file=sys.stderr)
    assert rc == 0
    tested = 0
    timestamp_2023 = datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp()
    timestamp_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
    for subdir in context.subdir, "noarch":
        if (tmp_path / subdir / "repodata.json").is_file():
            tested += 1
            channel = Channel(str(tmp_path / subdir))
            sd = SubdirData(channel)
            sd.load()
            assert all(
                timestamp_2023 <= rec.timestamp <= timestamp_2024 for rec in sd.iter_records()
            )
    assert tested
