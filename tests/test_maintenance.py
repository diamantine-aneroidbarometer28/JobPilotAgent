import time
from pathlib import Path

from app.maintenance import clean_generated


def test_clean_generated_defaults_to_dry_run(tmp_path: Path) -> None:
    artifact = tmp_path / "old.docx"
    artifact.write_bytes(b"document")
    old_time = time.time() - 40 * 86_400
    artifact.touch()
    import os

    os.utime(artifact, (old_time, old_time))

    matches = clean_generated(tmp_path, older_than_days=30)

    assert matches == [artifact]
    assert artifact.exists()


def test_clean_generated_apply_removes_only_old_docx(tmp_path: Path) -> None:
    old_artifact = tmp_path / "old.docx"
    recent_artifact = tmp_path / "recent.docx"
    ignored = tmp_path / "old.txt"
    for path in (old_artifact, recent_artifact, ignored):
        path.write_bytes(b"data")
    old_time = time.time() - 40 * 86_400
    import os

    os.utime(old_artifact, (old_time, old_time))
    os.utime(ignored, (old_time, old_time))

    clean_generated(tmp_path, older_than_days=30, dry_run=False)

    assert not old_artifact.exists()
    assert recent_artifact.exists()
    assert ignored.exists()
