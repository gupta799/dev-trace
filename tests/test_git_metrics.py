from __future__ import annotations

from devtrace.git_metrics import _parse_numstat


def test_parse_numstat_counts_text_and_binary_changes() -> None:
    parsed = _parse_numstat("2\t1\tfoo.py\n-\t-\timage.png\n3\t0\tbar.py\n")
    assert len(parsed) == 3
    assert parsed["foo.py"] == (2, 1)
    assert parsed["image.png"] == (0, 0)
    assert parsed["bar.py"] == (3, 0)
