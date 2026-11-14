import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from session_login import SessionLoginRequired, authorize_session, report_duplicated_session, select_session


class SessionLoginTests(unittest.IsolatedAsyncioTestCase):
    def test_railway_session_overrides_app_session(self):
        self.assertEqual(select_session({"session_string": "app-test"}, {"TG_SESSION": "railway-test"}), ("railway-test", True))

    def test_existing_saved_session_remains_supported(self):
        self.assertEqual(select_session({"session_string": "app-test"}, {}), ("app-test", False))

    async def test_redeploy_reuses_session_without_requesting_code(self):
        api = SimpleNamespace(post_bridge=AsyncMock())
        login = AsyncMock()
        for _ in range(2):
            client = SimpleNamespace(is_user_authorized=AsyncMock(return_value=True), session=SimpleNamespace(save=Mock(return_value="test-session")))
            await authorize_session(api, client, {}, "test-session", True, login)
        login.assert_not_awaited()
        self.assertEqual(api.post_bridge.await_count, 2)
        api.post_bridge.assert_awaited_with({"session_string": "test-session", "clear_code": True, "status": "running"})

    async def test_revoked_explicit_session_never_requests_login_code(self):
        api = SimpleNamespace(post_bridge=AsyncMock())
        client = SimpleNamespace(is_user_authorized=AsyncMock(return_value=False))
        login = AsyncMock()
        with self.assertRaises(SessionLoginRequired):
            await authorize_session(api, client, {}, "revoked-test", True, login)
        login.assert_not_awaited()
        api.post_bridge.assert_awaited_once_with({"status": "restart_needed"})

    async def test_no_session_preserves_optional_code_login(self):
        api = SimpleNamespace(post_bridge=AsyncMock())
        client = SimpleNamespace(is_user_authorized=AsyncMock(return_value=False))
        login = AsyncMock()
        await authorize_session(api, client, {}, None, False, login)
        login.assert_awaited_once_with(api, client, {})

    async def test_duplicated_session_is_cleared_and_marked_for_restart(self):
        api = SimpleNamespace(post_bridge=AsyncMock())
        await report_duplicated_session(api)
        api.post_bridge.assert_awaited_once_with({"session_string": None, "status": "restart_needed"})


if __name__ == "__main__":
    unittest.main()