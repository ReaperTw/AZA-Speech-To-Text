import unittest

from paste_target import TERMINAL_CLASS_NAMES, capture_foreground, paste_text


class FakeUser32:
    def __init__(self, class_name="OtherWindow"):
        self.class_name = class_name
        self.calls = []

    def GetForegroundWindow(self):
        self.calls.append(("foreground",))
        return 123

    def SetForegroundWindow(self, hwnd):
        self.calls.append(("foreground_set", hwnd))

    def GetClassNameW(self, hwnd, buffer, _size):
        self.calls.append(("class", hwnd))
        buffer.value = self.class_name
        return len(self.class_name)


class PasteTargetTests(unittest.TestCase):
    def test_capture_foreground_returns_int_and_rejects_zero(self):
        user32 = FakeUser32()
        self.assertEqual(capture_foreground(user32), 123)

        user32.GetForegroundWindow = lambda: 0
        self.assertIsNone(capture_foreground(user32))

    def test_empty_text_returns_false_without_side_effects(self):
        copied = []
        sent = []

        result = paste_text(
            "",
            clipboard_copy=copied.append,
            send_keys=sent.append,
        )

        self.assertFalse(result)
        self.assertEqual(copied, [])
        self.assertEqual(sent, [])

    def test_non_terminal_window_sends_ctrl_v(self):
        user32 = FakeUser32("NotTerminal")
        copied = []
        sent = []

        result = paste_text(
            "hello",
            123,
            user32=user32,
            clipboard_copy=copied.append,
            send_keys=sent.append,
        )

        self.assertTrue(result)
        self.assertEqual(copied, ["hello"])
        self.assertEqual(sent, ["ctrl+v"])

    def test_terminal_windows_send_ctrl_shift_v(self):
        for class_name in TERMINAL_CLASS_NAMES:
            with self.subTest(class_name=class_name):
                user32 = FakeUser32(class_name)
                sent = []

                result = paste_text(
                    "hello",
                    123,
                    user32=user32,
                    clipboard_copy=lambda _text: None,
                    send_keys=sent.append,
                )

                self.assertTrue(result)
                self.assertEqual(sent, ["ctrl+shift+v"])

    def test_set_foreground_happens_before_send(self):
        user32 = FakeUser32()
        events = []
        user32.SetForegroundWindow = lambda hwnd: events.append(("set", hwnd))
        send_keys = lambda chord: events.append(("send", chord))

        self.assertTrue(
            paste_text(
                "hello",
                123,
                user32=user32,
                clipboard_copy=lambda _text: events.append(("copy",)),
                send_keys=send_keys,
            )
        )

        self.assertLess(events.index(("set", 123)), events.index(("send", "ctrl+v")))

    def test_send_exception_returns_false(self):
        def send_keys(_chord):
            raise RuntimeError("send failed")

        self.assertFalse(
            paste_text(
                "hello",
                clipboard_copy=lambda _text: None,
                send_keys=send_keys,
            )
        )


if __name__ == "__main__":
    unittest.main()
