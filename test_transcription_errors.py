import tempfile
import unittest
from pathlib import Path

from transcription_errors import (
    error_message,
    present_error,
    retry_action,
    transcribe_with_rotation,
)


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


class BadRequestError(Exception):
    pass


class FakeTranscriptions:
    def __init__(self, outcomes, calls):
        self.outcomes = iter(outcomes)
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes, calls):
        self.audio = type("Audio", (), {})()
        self.audio.transcriptions = FakeTranscriptions(outcomes, calls)


class TranscriptionErrorsTests(unittest.TestCase):
    def make_upload(self):
        temporary_directory = tempfile.TemporaryDirectory()
        upload_path = Path(temporary_directory.name) / "recording.wav"
        upload_path.write_bytes(b"audio bytes")
        self.addCleanup(temporary_directory.cleanup)
        return upload_path

    def test_retry_action_and_messages_use_public_error_shape(self):
        cases = (
            (type("Unauthorized", (Exception,), {"status_code": 401})("raw exception gsk_auth"), "next_key", "API key"),
            (RateLimitError("secret gsk_rate"), "retry", "額度或速率限制"),
            (type("APITimeoutError", (Exception,), {})("raw exception gsk_timeout"), "retry", "網路逾時"),
            (type("ServerError", (Exception,), {"status_code": 503})("raw exception gsk_server"), "retry", "服務暫時不可用"),
            (BadRequestError("raw exception gsk_bad"), "fail", "這段錄音無法辨識"),
            (Exception("raw exception gsk_unknown"), "fail", "辨識失敗"),
        )
        for error, action, expected_message in cases:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(retry_action(error), action)
                message = error_message(error)
                self.assertIn(expected_message, message)
                self.assertNotIn("gsk_", message)
                self.assertNotIn(str(error), message)

    def test_present_error_maps_workflow_reasons_and_preserves_cjk(self):
        mappings = {
            "Groq returned no spoken content.": "沒有辨到語音。請靠近麥克風再說一次。",
            "No audio frames were recorded.": "沒有錄到聲音。請再錄一次。",
            "The recording could not be saved.": "無法儲存錄音。請再錄一次。",
            "The transcription was copied, but automatic paste failed.": "文字已複製到剪貼簿，但自動貼上失敗。請自行貼上。",
            "Microphone start timed out.": "麥克風沒有及時啟動。請再試一次。",
            "Recording failed: device unavailable": "無法錄音。請檢查麥克風後再試一次。",
            "Recording was too short.": "錄音太短。請再說一次。",
            "Transcription was cancelled.": "已取消這次辨識。",
            "other workflow reason": "辨識失敗。請在通知區開啟記錄檔查看。",
        }
        for source, expected in mappings.items():
            with self.subTest(source=source):
                self.assertEqual(present_error(source), expected)
        already_present = "已有中文訊息。"
        self.assertEqual(present_error(already_present), already_present)

    def test_recording_failure_with_cjk_device_name_stays_actionable(self):
        self.assertEqual(
            present_error("Recording failed: 麥克風忙碌 gsk_secret"),
            "無法錄音。請檢查麥克風後再試一次。",
        )

    def test_failed_attempt_logs_redacted_error(self):
        upload_path = self.make_upload()
        calls = []
        client = FakeClient([BadRequestError("raw gsk_secret")], calls)

        with self.assertLogs("aza_stt", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                transcribe_with_rotation(
                    upload_path,
                    "prompt",
                    ["gsk_" + ("a" * 20)],
                    ["whisper-large-v3"],
                    lambda _key: client,
                    lambda _seconds: None,
                )

        logged = "\n".join(logs.output)
        self.assertIn("gsk_[redacted]", logged)
        self.assertNotIn("gsk_secret", logged)
        self.assertNotIn("gsk_" + ("a" * 20), logged)

    def test_next_key_skips_second_model_and_does_not_sleep(self):
        upload_path = self.make_upload()
        calls = []
        clients = {
            "gsk_first": FakeClient([AuthenticationError("raw gsk_first")], calls),
            "gsk_second": FakeClient(["success"], calls),
        }
        factory_keys = []
        sleeps = []

        def client_factory(api_key):
            factory_keys.append(api_key)
            return clients[api_key]

        result = transcribe_with_rotation(
            upload_path,
            "prompt",
            ["gsk_first", "gsk_second"],
            ["model-a", "model-b"],
            client_factory,
            sleeps.append,
        )

        self.assertEqual(result, ("success", 1, 0))
        self.assertEqual(factory_keys, ["gsk_first", "gsk_second"])
        self.assertEqual([call["model"] for call in calls], ["model-a", "model-a"])
        self.assertEqual(sleeps, [])

    def test_fail_stops_after_one_api_call(self):
        upload_path = self.make_upload()
        calls = []
        client = FakeClient([BadRequestError("raw gsk_bad")], calls)

        with self.assertRaisesRegex(RuntimeError, "這段錄音無法辨識"):
            transcribe_with_rotation(
                upload_path,
                "prompt",
                ["gsk_bad", "gsk_unused"],
                ["model-a", "model-b"],
                lambda api_key: client,
                lambda seconds: self.fail("fail must not sleep"),
            )

        self.assertEqual(len(calls), 1)

    def test_retry_walks_models_then_next_key(self):
        upload_path = self.make_upload()
        calls = []
        clients = {
            "gsk_first": FakeClient(
                [RateLimitError("first gsk"), RateLimitError("second gsk")], calls
            ),
            "gsk_second": FakeClient(["success"], calls),
        }
        sleeps = []

        result = transcribe_with_rotation(
            upload_path,
            "prompt",
            ["gsk_first", "gsk_second"],
            ["model-a", "model-b"],
            lambda api_key: clients[api_key],
            sleeps.append,
        )

        self.assertEqual(result, ("success", 1, 0))
        self.assertEqual(
            [(call["model"], call["file"][1]) for call in calls],
            [("model-a", b"audio bytes"), ("model-b", b"audio bytes"), ("model-a", b"audio bytes")],
        )
        self.assertEqual(sleeps, [0.5, 0.5])

    def test_cancelled_attempt_skips_client_and_api(self):
        upload_path = self.make_upload()
        factory_calls = []
        api_calls = []

        def client_factory(api_key):
            factory_calls.append(api_key)
            return FakeClient(["unexpected"], api_calls)

        with self.assertRaisesRegex(RuntimeError, "已取消這次辨識"):
            transcribe_with_rotation(
                upload_path,
                "prompt",
                ["gsk_key"],
                ["model-a"],
                client_factory,
                lambda seconds: self.fail("cancelled attempt must not sleep"),
                is_cancelled=lambda: True,
            )

        self.assertEqual(factory_calls, [])
        self.assertEqual(api_calls, [])


if __name__ == "__main__":
    unittest.main()
