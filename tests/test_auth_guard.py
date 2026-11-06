from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from auth_guard import ManualLoginRequired, login_block_reason
from automation_engine import GoogleUltraAutomator


class LoginBlockTests(TestCase):
    def test_rejected_url_and_translated_messages(self):
        cases = [
            ("https://accounts.google.com/v3/signin/rejected", ""),
            ("https://accounts.google.com/signin", "We couldn’t verify it’s you"),
            ("https://accounts.google.com/signin", "此浏览器或应用可能不安全"),
            ("https://accounts.google.com/challenge/recaptcha", ""),
            ("https://accounts.google.com/signin", "Add 2-Step Verification"),
        ]
        for url, body in cases:
            with self.subTest(url=url, body=body):
                self.assertTrue(login_block_reason(url, body))

    def test_normal_or_unrelated_page_is_not_rejected(self):
        self.assertEqual(login_block_reason("https://accounts.google.com/signin", "Email or phone"), "")
        self.assertEqual(login_block_reason("https://example.com/?next=signin/rejected", "not a robot"), "")


class AuthenticationTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.logs = []
        self.instance = GoogleUltraAutomator(
            {"id": "test", "email": "test@example.invalid", "password": "unused"},
            {}, on_log=self.logs.append,
        )
        self.page = Mock()
        self.page.is_closed.return_value = False
        self.page.inner_text = AsyncMock(return_value="We couldn’t verify it’s you")
        self.page.url = "https://accounts.google.com/v3/signin/rejected"

    async def test_rejection_stops_before_any_login_interaction(self):
        with self.assertRaises(ManualLoginRequired):
            await self.instance.pass_reauth_on_page(self.page)
        self.page.locator.assert_not_called()

    async def test_public_plans_page_without_session_is_not_success(self):
        self.page.url = "https://one.google.com/plans"
        self.page.context.cookies = AsyncMock(return_value=[])
        with self.assertRaises(ManualLoginRequired):
            await self.instance.require_authenticated_session(self.page)

    async def test_login_with_session_is_accepted(self):
        self.page.url = "https://one.google.com/plans"
        self.page.context.cookies = AsyncMock(return_value=[{"name": "SID", "value": "test-session"}])
        await self.instance.require_authenticated_session(self.page)

    async def test_step1_rejection_never_reports_completion(self):
        with patch.object(self.instance, "safe_goto", new=AsyncMock()), \
             patch.object(self.instance, "save_screenshot", new=AsyncMock()), \
             patch.object(self.instance, "pass_reauth_on_page", new=AsyncMock(side_effect=ManualLoginRequired("rejected"))), \
             patch("automation_engine.asyncio.sleep", new=AsyncMock()):
            self.page.locator.return_value.count = AsyncMock(return_value=0)
            self.page.locator.return_value.first.is_visible = AsyncMock(return_value=False)
            with self.assertRaises(ManualLoginRequired):
                await self.instance.step1_login(self.page)
        self.assertFalse(any("Step 1 完成" in line for line in self.logs))
