import os
import socket
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import automation_engine as engine
from auth_guard import ManualLoginRequired
from browser_runtime import ensure_debug_port_available, find_chrome_path


class BrowserRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def automator(self, port):
        states = []
        instance = engine.GoogleUltraAutomator(
            account={"id": "runtime-test", "email": "test@example.invalid"},
            card={}, port=port, on_log=lambda _: None, on_state=states.append,
        )
        return instance, states

    async def test_occupied_port_does_not_kill_or_launch(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            instance, states = self.automator(port)
            with patch.object(engine, "launch_chrome") as launch:
                await instance.run_pipeline(start_step=5)
            launch.assert_not_called()
            self.assertEqual(states[-1]["status"], "error")
            # The original listener still accepts connections.
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass

    async def test_missing_chrome_reports_error(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        instance, states = self.automator(port)
        with patch.object(engine, "CHROME_PATH", "/nonexistent/chrome"):
            await instance.run_pipeline(start_step=5)
        self.assertEqual(states[-1]["status"], "error")
        self.assertIn("找不到 Chrome", states[-1]["step_message"])

    async def test_startup_timeout_cleans_up_child(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        instance, states = self.automator(port)
        with patch.object(engine, "launch_chrome") as launch, \
             patch.object(engine, "wait_for_chrome", new=AsyncMock(side_effect=RuntimeError("startup timeout"))), \
             patch.object(engine, "stop_chrome") as stop:
            await instance.run_pipeline(start_step=5)
        stop.assert_called_once_with(launch.return_value)
        self.assertEqual(states[-1]["status"], "error")

    @unittest.skipUnless(find_chrome_path(), "Chrome is not installed")
    async def test_manual_login_stops_pipeline_and_cleans_up(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        instance, states = self.automator(port)
        # Synthetic data only; all Google/checkout steps below are replaced.
        instance.card = {"number": "0" * 16, "exp_month": "01", "exp_year": "99", "cvc": "000"}
        with tempfile.TemporaryDirectory(prefix="chrome-runtime-test-") as profile:
            with patch.object(engine, "get_profile_dir", return_value=profile), \
                 patch.object(instance, "verify_ip_environment", new=AsyncMock()), \
                 patch.object(instance, "step1_login", new=AsyncMock(side_effect=ManualLoginRequired("manual login"))), \
                 patch.object(instance, "step2_layer1_12m", new=AsyncMock()) as checkout, \
                 patch.dict(os.environ, {"CHROME_HEADLESS": "1"}):
                await instance.run_pipeline()
            checkout.assert_not_awaited()
            self.assertEqual(states[-1]["status"], "needs_login")
            self.assertIsNotNone(instance.proc.poll())

    @unittest.skipUnless(find_chrome_path(), "Chrome is not installed")
    async def test_real_headless_chrome_pipeline_and_cleanup(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        instance, states = self.automator(port)

        async def local_step(page):
            await page.set_content("<title>Isolated runtime test</title><h1>macOS Chrome OK</h1>")
            self.assertEqual(await page.title(), "Isolated runtime test")

        with tempfile.TemporaryDirectory(prefix="chrome-runtime-test-") as profile:
            with patch.object(engine, "get_profile_dir", return_value=profile), \
                 patch.object(instance, "verify_ip_environment", new=AsyncMock()), \
                 patch.object(instance, "step5_cancel_and_verify", new=AsyncMock(side_effect=local_step)) as step, \
                 patch.dict(os.environ, {"CHROME_HEADLESS": "1"}):
                await instance.run_pipeline(start_step=5)
            step.assert_awaited_once()
            self.assertFalse(any(s.get("status") == "error" for s in states), states)
            self.assertIsNotNone(instance.proc.poll())
            ensure_debug_port_available(port)


if __name__ == "__main__":
    unittest.main()
