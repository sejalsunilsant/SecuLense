import gc
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from secu_lense.server.auth import AuthStore


class TestLocalAuth(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def test_first_account_password_hash_and_session_lifecycle(self):
        store = AuthStore(self.tmp_path / "auth.sqlite3")

        user = store.create_first_user("analyst_1", "correct horse battery")
        self.assertEqual(user["username"], "analyst_1")
        self.assertEqual(store.user_count(), 1)
        self.assertEqual(store.authenticate("analyst_1", "correct horse battery"), user)
        self.assertIsNone(store.authenticate("analyst_1", "not the password"))

        token, expires = store.create_session(user["id"])
        self.assertTrue(bool(expires))
        self.assertEqual(store.get_session_user(token), user)
        store.revoke_session(token)
        self.assertIsNone(store.get_session_user(token))

        with self.assertRaises(RuntimeError):
            store.create_first_user("another_user", "a different long password")

        with sqlite3.connect(store.path) as db:
            password_hash = db.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotEqual(password_hash, b"correct horse battery")

    def test_additional_local_accounts_can_sign_up_with_unique_names(self):
        store = AuthStore(self.tmp_path / "auth.sqlite3")
        owner = store.create_first_user("owner", "correct horse battery")
        member = store.create_user("member_1", "another long password")

        self.assertEqual(store.user_count(), 2)
        self.assertEqual(store.authenticate("member_1", "another long password"), member)
        self.assertNotEqual(member["id"], owner["id"])
        with self.assertRaises(ValueError):
            store.create_user("member_1", "yet another long password")

    def test_first_account_rejects_weak_credentials(self):
        store = AuthStore(self.tmp_path / "auth.sqlite3")
        for username, password in [("ab", "long enough password"), ("valid_user", "short")]:
            with self.assertRaises(ValueError):
                store.create_first_user(username, password)
        self.assertEqual(store.user_count(), 0)


if __name__ == "__main__":
    unittest.main()
