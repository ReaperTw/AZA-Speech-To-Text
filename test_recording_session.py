import threading
import time
import unittest

from recording_session import (
    clip_rejection,
    duration_seconds,
    hit_duration_cap,
    arm_recording_start,
    note_hold_release,
)


class FakeRoot:
    def __init__(self):
        self.callbacks = []

    def after(self, _delay, callback):
        self.callbacks.append(callback)


class FakeApp:
    def __init__(self, recording_started_event=None):
        self.root = FakeRoot()
        self.recording_started_event = recording_started_event or threading.Event()
        self.capture_ready = False
        self.is_recording = False
        self.frames = [b"old"]
        self.recording_error = "old error"
        self.stop_after_open = True
        self.paste_hwnd = None
        self.ui_errors = []
        self.ui_recording_calls = 0
        self.stop_calls = 0

    def set_ui_error(self, message):
        self.ui_errors.append(message)

    def set_ui_recording(self):
        self.ui_recording_calls += 1

    def stop_recording_process(self):
        self.stop_calls += 1


def wait_until(predicate, timeout=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


class RecordingSessionTests(unittest.TestCase):
    def test_duration_and_recording_boundaries(self):
        self.assertEqual(duration_seconds(0), 0)
        self.assertAlmostEqual(duration_seconds(399, chunk=1, rate=1000), 0.399)
        self.assertEqual(
            clip_rejection(0),
            "No audio frames were recorded.",
        )
        self.assertEqual(
            clip_rejection(399, chunk=1, rate=1000),
            "Recording was too short.",
        )
        self.assertIsNone(clip_rejection(400, chunk=1, rate=1000))
        self.assertFalse(hit_duration_cap(239, chunk=1, rate=1, max_seconds=240))
        self.assertTrue(hit_duration_cap(240, chunk=1, rate=1, max_seconds=240))

    def test_arm_returns_while_start_watcher_is_still_waiting(self):
        class BlockingEvent:
            def __init__(self):
                self.wait_started = threading.Event()
                self.release = threading.Event()

            def clear(self):
                pass

            def wait(self, timeout):
                self.wait_started.set()
                return self.release.wait(timeout)

        started_event = BlockingEvent()
        app = FakeApp(started_event)
        start_thread_called = threading.Event()
        try:
            started_at = time.monotonic()
            arm_recording_start(
                app,
                lambda: 123,
                timeout_seconds=0.5,
                start_thread=start_thread_called.set,
            )
            elapsed = time.monotonic() - started_at

            self.assertLess(elapsed, 0.25)
            self.assertTrue(start_thread_called.is_set())
            self.assertTrue(started_event.wait_started.wait(0.25))
        finally:
            started_event.release.set()

    def test_hold_release_during_microphone_open_is_deferred(self):
        app = FakeApp()
        arm_recording_start(app, lambda: 123, 0.5, lambda: None)

        self.assertEqual(note_hold_release(app), "defer")
        self.assertTrue(app.stop_after_open)

        app.recording_started_event.set()
        self.assertTrue(wait_until(lambda: len(app.root.callbacks) == 1))
        app.root.callbacks.pop(0)()
        self.assertEqual(app.stop_calls, 1)

    def test_hold_release_when_capture_is_ready_stops_now(self):
        app = FakeApp()
        app.capture_ready = True

        self.assertEqual(note_hold_release(app), "stop_now")
        self.assertFalse(app.stop_after_open)

    def test_timeout_reports_exact_microphone_error(self):
        app = FakeApp()
        arm_recording_start(app, lambda: 123, 0.01, lambda: None)

        self.assertTrue(wait_until(lambda: len(app.root.callbacks) == 1))
        self.assertFalse(app.is_recording)
        app.root.callbacks.pop(0)()
        self.assertEqual(app.ui_errors, ["Microphone start timed out."])
        self.assertEqual(app.ui_recording_calls, 0)

    def test_start_success_updates_recording_ui(self):
        app = FakeApp()

        def start_thread():
            app.recording_started_event.set()

        arm_recording_start(app, lambda: 123, 0.5, start_thread)

        self.assertTrue(wait_until(lambda: len(app.root.callbacks) == 1))
        app.root.callbacks.pop(0)()
        self.assertEqual(app.ui_recording_calls, 1)
        self.assertEqual(app.stop_calls, 0)


if __name__ == "__main__":
    unittest.main()
