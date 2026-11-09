from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from compose_backup import backup, database_container, restore


def test_existing_backup_file_is_never_overwritten(tmp_path):
    target = tmp_path / 'archive.dump'
    target.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        backup('unused', target)
    assert target.read_bytes() == b'preserve'


def test_restore_rejects_unapproved_target_without_docker(tmp_path, monkeypatch):
    source = tmp_path / 'archive.dump'
    source.write_bytes(b'example')
    called = []
    monkeypatch.setattr('compose_backup.docker', lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError):
        restore('unused', source, 'supportops')
    assert not called


def test_invalid_project_rejected_without_docker(monkeypatch):
    called = []
    monkeypatch.setattr('compose_backup.docker', lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError):
        database_container('../other-project')
    assert not called


def test_remote_docker_context_is_rejected(monkeypatch):
    from types import SimpleNamespace
    calls = []
    def fake_docker(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout='tcp://example.invalid:2376')
    monkeypatch.setattr('compose_backup.docker', fake_docker)
    with pytest.raises(RuntimeError):
        database_container('testproject')
    assert calls == [('context', 'inspect', '--format', '{{.Endpoints.docker.Host}}')]
