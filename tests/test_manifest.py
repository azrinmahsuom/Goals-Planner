import pytest

from analysis import manifest


@pytest.fixture
def snapshot(tmp_path):
    """A raw folder with two recorded files and its manifest."""
    raw = tmp_path / "raw"
    (raw / "src").mkdir(parents=True)
    path = tmp_path / "MANIFEST.yaml"
    for name in ("a.csv", "b.csv"):
        f = raw / "src" / name
        f.write_text(f"{name},1\n")
        manifest.record(f, {"source": name, "retrieved": "2026-10-28"}, path, raw)
    return raw, path


def test_sha256_of_known_bytes(tmp_path):
    f = tmp_path / "x.txt"
    f.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert manifest.sha256(f) == expected


def test_unchanged_files_are_ok(snapshot):
    raw, path = snapshot
    status = manifest.verify_data(path, raw)
    assert sorted(status["ok"]) == ["src/a.csv", "src/b.csv"]
    assert status["changed"] == status["missing"] == []


def test_changed_file_is_drift_not_failure(snapshot, tmp_path):
    raw, path = snapshot
    (raw / "src" / "a.csv").write_text("revised,2\n")
    status = manifest.verify_data(path, raw)  # does not raise
    assert status["changed"] == ["src/a.csv"]
    report = manifest.write_drift_report(status, path, tmp_path / "drift.md")
    assert "| src/a.csv | 2026-10-28 | a.csv |" in report.read_text()


def test_missing_file_stops_the_run(snapshot):
    raw, path = snapshot
    (raw / "src" / "b.csv").unlink()
    with pytest.raises(manifest.DataVerificationError, match="src/b.csv"):
        manifest.verify_data(path, raw)


def test_drift_report_when_nothing_changed(snapshot, tmp_path):
    raw, path = snapshot
    status = manifest.verify_data(path, raw)
    report = manifest.write_drift_report(status, path, tmp_path / "drift.md")
    assert "No raw file differs" in report.read_text()
