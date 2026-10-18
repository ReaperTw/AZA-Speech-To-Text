import threading


MIN_RECORDING_SECONDS = 0.4
MAX_RECORDING_SECONDS = 240.0


def duration_seconds(frame_count, chunk=1024, rate=16000) -> float:
    return frame_count * chunk / rate


def clip_rejection(frame_count, chunk=1024, rate=16000):
    """Return a rejection reason, or None when the clip should be uploaded."""
    if frame_count == 0:
        return "No audio frames were recorded."
    if duration_seconds(frame_count, chunk, rate) < MIN_RECORDING_SECONDS:
        return "Recording was too short."
    return None


def hit_duration_cap(
    frame_count, chunk=1024, rate=16000, max_seconds=MAX_RECORDING_SECONDS
) -> bool:
    """Return whether the recording duration has reached its maximum."""
    return duration_seconds(frame_count, chunk, rate) >= max_seconds


def arm_recording_start(app, capture_foreground, timeout_seconds, start_thread):
    """Start recording without blocking the hotkey thread on microphone setup."""
    app.paste_hwnd = capture_foreground()
    app.is_recording = True
    app.frames = []
    app.recording_error = None
    app.stop_after_open = False
    app.recording_started_event.clear()
    start_thread()

    def watch_recording_start():
        if not app.recording_started_event.wait(timeout_seconds):
            app.is_recording = False
            app.root.after(
                0,
                lambda: app.set_ui_error("Microphone start timed out."),
            )
            return
        if app.recording_error:
            return
        if not app.is_recording:
            return
        if app.stop_after_open:
            app.root.after(0, app.stop_recording_process)
        else:
            app.root.after(0, app.set_ui_recording)

    threading.Thread(target=watch_recording_start, daemon=True).start()


def note_hold_release(app) -> str:
    """Record a hold release that occurs while microphone setup is pending."""
    if app.capture_ready:
        app.stop_after_open = False
        return "stop_now"
    app.stop_after_open = True
    return "defer"
