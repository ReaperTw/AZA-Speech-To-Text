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


def microphone_open_outcome(timed_out, recording_error, is_recording, stop_after_open):
    """Return 'timeout', 'stop', 'recording', or None after the open wait."""
    if timed_out:
        return "timeout"
    if recording_error or not is_recording:
        return None
    if stop_after_open:
        return "stop"
    return "recording"
