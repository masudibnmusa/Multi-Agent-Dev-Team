import pytest

from team.main import main


@pytest.mark.parametrize("flag", [["--max-rounds", "0"], ["--budget", "0"]])
def test_bad_limits_rejected(flag):
    with pytest.raises(SystemExit) as e:
        main(["build", "x", *flag])
    assert e.value.code == 2


def test_timeline_viewer_without_runs(monkeypatch, tmp_path):
    from team.observability import timeline_viewer

    monkeypatch.setattr(timeline_viewer, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["timeline_viewer"])
    with pytest.raises(SystemExit, match="No runs found"):
        timeline_viewer.main()
