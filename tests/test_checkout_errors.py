from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, Mock, patch

from automation_engine import GoogleUltraAutomator
from checkout_errors import CheckoutUnavailable, checkout_unavailable_reason


REFUSAL = "Google One\n不可订阅\nYouTube Premium Individual Add On无法使用。您可以单独订阅此套装中的其他商品。\n知道了"


class CheckoutErrorTests(TestCase):
    def test_observed_addon_error_has_specific_reason(self):
        self.assertIn("YouTube Premium Individual Add On", checkout_unavailable_reason(REFUSAL))

    def test_english_refusal(self):
        self.assertTrue(checkout_unavailable_reason("Can't subscribe\nThis subscription is unavailable."))

    def test_normal_checkout_and_incidental_words_are_not_refusal(self):
        self.assertEqual(checkout_unavailable_reason("Google One\nSubscribe\nFree trial"), "")
        self.assertEqual(checkout_unavailable_reason("如果不可订阅，请联系支持"), "")


class CheckoutPollingTests(IsolatedAsyncioTestCase):
    async def test_explicit_refusal_stops_before_click_or_retry(self):
        instance = GoogleUltraAutomator({"id": "test", "email": "test@example.invalid"}, {}, on_log=lambda _: None)
        page = Mock()
        page.inner_text = AsyncMock(return_value=REFUSAL)
        with patch.object(instance, "save_screenshot", new=AsyncMock()) as screenshot:
            with self.assertRaises(CheckoutUnavailable):
                await instance._poll_eacquire_modal(page, max_loops=60)
        screenshot.assert_awaited_once()
        page.evaluate.assert_not_called()
        page.inner_text.assert_awaited_once()
        self.assertIn("当前套餐组合不可订阅", instance.last_subscribe_error)
