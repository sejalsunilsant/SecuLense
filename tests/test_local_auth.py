import sqlite3

import pytest

from scripts.local_web_server import AuthStore


def test_first_account_password_hash_and_session_lifecycle(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")

    user = store.create_first_user("analyst_1", "correct horse battery")
    assert user["username"] == "analyst_1"
    assert store.user_count() == 1
    assert store.authenticate("analyst_1", "correct horse battery") == user
    assert store.authenticate("analyst_1", "not the password") is None

    token, expires = store.create_session(user["id"])
    assert expires
    assert store.get_session_user(token) == user
    store.revoke_session(token)
    assert store.get_session_user(token) is None

    with pytest.raises(RuntimeError, match="Setup is already complete"):
        store.create_first_user("another_user", "a different long password")

    with sqlite3.connect(store.path) as db:
        password_hash = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert password_hash != b"correct horse battery"


def test_additional_local_accounts_can_sign_up_with_unique_names(tmp_path):
    store = AuthStore(tmp_path / "auth.sqlite3")
    owner = store.create_first_user("owner", "correct horse battery")
    member = store.create_user("member_1", "another long password")

    assert store.user_count() == 2
    assert store.authenticate("member_1", "another long password") == member
    assert member["id"] != owner["id"]
    with pytest.raises(ValueError, match="already in use"):
        store.create_user("member_1", "yet another long password")


@pytest.mark.parametrize(
    ("username", "password"),
    [("ab", "long enough password"), ("valid_user", "short")],
)
def test_first_account_rejects_weak_credentials(tmp_path, username, password):
    store = AuthStore(tmp_path / "auth.sqlite3")
    with pytest.raises(ValueError):
        store.create_first_user(username, password)
    assert store.user_count() == 0
