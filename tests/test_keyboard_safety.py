import json
import os
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch

import groq_dictate as stt


class KeyboardSafetyTests(unittest.TestCase):
    def setUp(self):
        # Exercise the real dispatch engine without installing desktop-wide hooks.
        listener = stt.keyboard._KeyboardListener()
        listener.init()
        listener_patch = patch.object(stt.keyboard, "_listener", listener)
        listener_patch.start()
        self.addCleanup(listener_patch.stop)
        startup_patch = patch.object(listener, "start_if_necessary")
        startup_patch.start()
        self.addCleanup(startup_patch.stop)

    def test_key_selection_does_not_swallow_typing_or_modifier_releases(self):
        capture = stt.RecordKeySetupDialog.__new__(stt.RecordKeySetupDialog)
        capture.stop_capture = Mock()
        capture.capture_status_var = Mock()
        capture.capture_button = Mock()
        capture.capture_queue = queue.Queue()
        capture.ui = lambda text: text
        capture.after = Mock(return_value="capture-timer")
        with patch.object(stt.pynput_mouse, "Listener"):
            capture.begin_capture()
            try:
                for key in ("w", "a", "s", "d", "enter", "left windows", "ctrl"):
                    code = stt.keyboard.key_to_scan_codes(key)[0]
                    for event_type in (stt.keyboard.KEY_DOWN, stt.keyboard.KEY_UP):
                        with self.subTest(key=key, event_type=event_type):
                            event = stt.keyboard.KeyboardEvent(event_type, code, name=key)
                            self.assertTrue(stt.keyboard._listener.direct_callback(event))
            finally:
                stt.keyboard.unhook(capture.capture_keyboard_hook)

    def test_non_windows_modifiers_cannot_be_standalone_recording_controls(self):
        for key in ("ctrl", "left ctrl", "alt", "right alt", "shift", "right shift"):
            with self.subTest(key=key):
                self.assertIsNone(stt.normalize_record_key(key))

    def test_existing_windows_key_setting_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"record_key": "left windows", "activation_mode": "double_press"}, stream)
            self.assertEqual(stt.load_user_input_settings(path), ("left windows", "double_press"))
            self.assertEqual(stt.save_user_input_settings("left windows", "hold", path), ("left windows", "hold"))
            self.assertEqual(stt.load_user_input_settings(path), ("left windows", "hold"))

    def test_dedicated_left_windows_consumes_only_selected_key(self):
        app = stt.GroqDictateApp.__new__(stt.GroqDictateApp)
        app.record_key = "left windows"
        app.activation_mode = "hold"
        app.keyboard_hooks = []
        app.mouse_listener = None
        app.is_processing_ui = False
        app.is_recording = False
        app.capture_ready = True
        app.stop_after_open = False
        app.start_recording_process = lambda: setattr(app, "is_recording", True)
        app.stop_recording_process = lambda: setattr(app, "is_recording", False)

        def deliver(key, kind):
            code = stt.keyboard.key_to_scan_codes(key)[0]
            event = stt.keyboard.KeyboardEvent(kind, code, name=key)
            return stt.keyboard._listener.direct_callback(event)

        app.bind_record_key()
        try:
            self.assertFalse(deliver("left windows", stt.keyboard.KEY_DOWN))
            self.assertTrue(app.is_recording)
            for key in ("w", "a", "s", "d", "enter", "ctrl", "shift", "right windows"):
                for kind in (stt.keyboard.KEY_DOWN, stt.keyboard.KEY_UP):
                    with self.subTest(key=key, kind=kind):
                        self.assertTrue(deliver(key, kind))
                        self.assertTrue(app.is_recording)
            self.assertFalse(deliver("left windows", stt.keyboard.KEY_UP))
            self.assertFalse(app.is_recording)
            self.assertTrue(deliver("enter", stt.keyboard.KEY_DOWN))
            self.assertTrue(deliver("enter", stt.keyboard.KEY_UP))
        finally:
            app.unbind_record_key()
        self.assertTrue(deliver("left windows", stt.keyboard.KEY_DOWN))
        self.assertTrue(deliver("left windows", stt.keyboard.KEY_UP))
