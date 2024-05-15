from datetime import datetime, timezone

import pytest

from conda_subchannel.cli import date_argument


@pytest.mark.parametrize("inp,out",
    (   
        ["ts:1000", 1000.0],
        ["2024", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
        ["2024-1-1", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
        ["2024-01-01", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
        ["2024-01", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
        ["2024-1", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
        ["2024-1-1-0-0-0", datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()],
    )                         
)
def test_date_argument(inp, out):
    assert date_argument(inp) == out


@pytest.mark.parametrize("inp",
    (   
        "0",
        "-1",
        "ts:abc",
        "ts:2024-1",
    )                         
)
def test_bad_date_argument(inp):
    with pytest.raises(ValueError):
        date_argument(inp)
