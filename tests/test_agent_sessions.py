import io
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import console_agent


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.stdout = io.BytesIO(b"")
        self.returncode = None

    def poll(self):
        return self.returncode


class AgentSessionLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.temp.name) / "logs"
        self.counter = 20000
        self.counter_lock = threading.Lock()
        with console_agent._LOCK:
            console_agent._SESSIONS.clear()
        self.log_patch = patch.object(console_agent, "LOG_DIR", self.log_dir)
        self.limit_patch = patch.object(console_agent, "MAX_ACTIVE_PER_ENV", 1)
        self.popen_patch = patch.object(
            console_agent.subprocess, "Popen", side_effect=self.fake_popen
        )
        self.log_patch.start()
        self.limit_patch.start()
        self.popen_patch.start()

    def tearDown(self):
        self.popen_patch.stop()
        self.limit_patch.stop()
        self.log_patch.stop()
        with console_agent._LOCK:
            console_agent._SESSIONS.clear()
        self.temp.cleanup()

    def fake_popen(self, *_args, **_kwargs):
        # Keep the first call inside the admission critical section so the
        # second request has a chance to expose a check-then-start race.
        time.sleep(0.05)
        with self.counter_lock:
            self.counter += 1
            pid = self.counter
        return FakeProcess(pid)

    def test_concurrent_starts_cannot_exceed_per_environment_limit(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda _: console_agent._start(["fake-emulator"], "Fake", None),
                range(2),
            ))

        self.assertCountEqual([status for status, _payload in results], [202, 429])
        with console_agent._LOCK:
            running = sum(
                1 for record in console_agent._SESSIONS.values()
                if record["process"].poll() is None
            )
        self.assertEqual(running, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
