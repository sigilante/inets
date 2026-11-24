from inets.__main__ import main


def test_verbs_and_exit_codes(capsys, tmp_path):
    assert main(["check", "ivm"]) == 0
    assert main(["rules", "combinators"]) == 0
    assert main(["demo"]) == 0
    assert main(["run", "ski", "```SII0"]) == 0
    assert capsys.readouterr().out.strip().endswith("`00")
    assert main(["run", "ski", "``KI```SII``SII", "--lazy"]) == 0
    assert main(["run", "ski", "```SII``SII", "--rounds"]) == 1          # stops at the cap
    assert main(["run", "ski", "X"]) == 2                                 # not a term
    assert main(["check", str(tmp_path / "missing.rules")]) == 2
    bad = tmp_path / "bad.rules"
    bad.write_text("agent a 0\nagent b 0\nrule a >< a\n  => nothing\n  count x\n")
    assert main(["check", str(bad)]) == 1                                 # problems found
    assert main(["no-such-verb"]) == 2
    assert "Traceback" not in capsys.readouterr().err
