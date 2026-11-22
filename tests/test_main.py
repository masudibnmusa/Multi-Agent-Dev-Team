import pytest

from team.main import main


@pytest.mark.parametrize("flag", [["--max-rounds", "0"], ["--budget", "0"]])
def test_bad_limits_rejected(flag):
    with pytest.raises(SystemExit) as e:
        main(["build", "x", *flag])
    assert e.value.code == 2
