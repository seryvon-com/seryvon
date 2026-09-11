"""Tests for transactional session handling."""

import pytest

import seryvon.db.base as db_base


class _Session:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_session_scope_commits_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session()
    monkeypatch.setattr(db_base, "SessionLocal", lambda: session)
    with db_base.session_scope() as active:
        assert active is session
    assert session.committed is True
    assert session.closed is True


def test_session_scope_rolls_back_and_closes_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session()
    monkeypatch.setattr(db_base, "SessionLocal", lambda: session)
    with pytest.raises(RuntimeError, match="boom"), db_base.session_scope():
        raise RuntimeError("boom")
    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_register_jsonb_dumper() -> None:
    class Adapters:
        def __init__(self) -> None:
            self.calls: list[tuple[type[object], type[object]]] = []

        def register_dumper(self, python_type: type[object], dumper: type[object]) -> None:
            self.calls.append((python_type, dumper))

    class Connection:
        adapters = Adapters()

    db_base._register_jsonb_dumpers(Connection(), None)
    assert Connection.adapters.calls
    assert Connection.adapters.calls[0][0] is dict
