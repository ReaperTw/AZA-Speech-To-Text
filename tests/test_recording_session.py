import unittest

from recording_session import (
    clip_rejection,
    duration_seconds,
    hit_duration_cap,
    microphone_open_outcome,
)


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

    def test_microphone_open_outcome_prefers_timeout_then_failure(self):
        cases = (
            ((True, None, True, False), "timeout"),
            ((True, "mic failed", False, True), "timeout"),
            ((False, "mic failed", True, True), None),
            ((False, None, False, True), None),
            ((False, None, True, True), "stop"),
            ((False, None, True, False), "recording"),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(microphone_open_outcome(*args), expected)


if __name__ == "__main__":
    unittest.main()
