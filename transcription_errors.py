"""Error classification and bounded transcription retry rotation."""

import logging
import re


_LOGGER = logging.getLogger("aza_stt")
_SECRET = re.compile(r"gsk_\S+")


_NEXT_KEY = "next_key"
_RETRY = "retry"
_FAIL = "fail"

_NEXT_KEY_MESSAGE = "API key 無效。請在通知區重新輸入 Groq API key。"
_RETRY_MESSAGE = "額度或速率限制。請稍後再試，或更換 API key。"
_TIMEOUT_MESSAGE = "網路逾時。請檢查網路後再錄一次。"
_SERVICE_MESSAGE = "服務暫時不可用。請稍後再試。"
_RECORDING_MESSAGE = "這段錄音無法辨識。請再錄一次。"
_FAILURE_MESSAGE = "辨識失敗。請在通知區開啟記錄檔查看。"
_CANCELLED_MESSAGE = "已取消這次辨識。"


def _status_code(error):
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, str):
        try:
            return int(status_code)
        except ValueError:
            return status_code
    return status_code


def retry_action(error) -> str:
    """Return 'next_key', 'retry', or 'fail'."""
    status_code = _status_code(error)
    error_type = type(error).__name__

    if status_code in (401, 403) or error_type in {
        "AuthenticationError",
        "PermissionDeniedError",
    }:
        return _NEXT_KEY
    if status_code == 429 or error_type == "RateLimitError":
        return _RETRY
    if error_type in {
        "APITimeoutError",
        "APIConnectionError",
        "TimeoutError",
        "ConnectionError",
    }:
        return _RETRY
    if (isinstance(status_code, int) and 500 <= status_code <= 599) or error_type == "InternalServerError":
        return _RETRY
    if status_code in (400, 404, 409, 422) or error_type in {
        "BadRequestError",
        "NotFoundError",
        "ConflictError",
        "UnprocessableEntityError",
    }:
        return _FAIL
    return _FAIL


def error_message(error) -> str:
    """One Traditional Chinese actionable sentence. No exception text. No API key."""
    action = retry_action(error)
    if action == _NEXT_KEY:
        return _NEXT_KEY_MESSAGE
    if action == _FAIL:
        status_code = _status_code(error)
        error_type = type(error).__name__
        if status_code in (400, 404, 409, 422) or error_type in {
            "BadRequestError",
            "NotFoundError",
            "ConflictError",
            "UnprocessableEntityError",
        }:
            return _RECORDING_MESSAGE
        return _FAILURE_MESSAGE

    status_code = _status_code(error)
    error_type = type(error).__name__
    if status_code == 429 or error_type == "RateLimitError":
        return _RETRY_MESSAGE
    if error_type in {
        "APITimeoutError",
        "APIConnectionError",
        "TimeoutError",
        "ConnectionError",
    }:
        return _TIMEOUT_MESSAGE
    return _SERVICE_MESSAGE


def _contains_cjk(text):
    return any(
        (0x3400 <= ord(char) <= 0x4DBF)
        or (0x4E00 <= ord(char) <= 0x9FFF)
        or (0xF900 <= ord(char) <= 0xFAFF)
        or (0x20000 <= ord(char) <= 0x2FA1F)
        for char in text
    )


def present_error(message) -> str:
    """Map known English workflow reasons. Leave an already Chinese message unchanged."""
    text = message if isinstance(message, str) else str(message)
    if text.startswith("Recording failed:"):
        return "無法錄音。請檢查麥克風後再試一次。"
    exact_messages = {
        "Groq returned no spoken content.": "沒有辨到語音。請靠近麥克風再說一次。",
        "No audio frames were recorded.": "沒有錄到聲音。請再錄一次。",
        "The recording could not be saved.": "無法儲存錄音。請再錄一次。",
        "The transcription was copied, but automatic paste failed.": "文字已複製到剪貼簿，但自動貼上失敗。請自行貼上。",
        "Microphone start timed out.": "麥克風沒有及時啟動。請再試一次。",
        "Recording was too short.": "錄音太短。請再說一次。",
        "Transcription was cancelled.": _CANCELLED_MESSAGE,
    }
    if text in exact_messages:
        return exact_messages[text]
    if _contains_cjk(text):
        return text
    return _FAILURE_MESSAGE


def transcribe_with_rotation(
    upload_path,
    prompt,
    api_keys,
    models,
    client_factory,
    sleep,
    key_index=0,
    model_index=0,
    is_cancelled=None,
):
    """Return (transcription, key_index, model_index).
    Raise RuntimeError(error_message(last_error)) when attempts are exhausted or action is fail.
    Raise RuntimeError(present_error('Transcription was cancelled.')) if is_cancelled() is true between attempts.
    """
    if not api_keys or not models:
        raise RuntimeError(_FAILURE_MESSAGE)

    key_count = len(api_keys)
    model_count = len(models)
    key_index %= key_count
    model_index %= model_count
    attempted_pairs = set()
    tried_keys = set()
    blocked_keys = set()
    last_error = None

    while True:
        if is_cancelled is not None and is_cancelled():
            raise RuntimeError(present_error("Transcription was cancelled."))

        pair = (key_index, model_index)
        if pair in attempted_pairs:
            raise RuntimeError(error_message(last_error))
        attempted_pairs.add(pair)
        tried_keys.add(key_index)

        try:
            client = client_factory(api_keys[key_index])
            with open(upload_path, "rb") as upload_file:
                file_bytes = upload_file.read()
            transcription = client.audio.transcriptions.create(
                file=(upload_path, file_bytes),
                model=models[model_index],
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"],
                language="zh",
                prompt=prompt,
                temperature=0.0,
            )
        except Exception as error:
            last_error = error
            _LOGGER.info(
                "Groq attempt failed: key #%s, model %s, %s status=%s, %s",
                key_index + 1,
                models[model_index],
                type(error).__name__,
                _status_code(error),
                _SECRET.sub("gsk_[redacted]", str(error)),
            )
            action = retry_action(error)
            if action == _FAIL:
                raise RuntimeError(error_message(error)) from None
            if action == _NEXT_KEY:
                blocked_keys.add(key_index)
                next_key = (key_index + 1) % key_count
                if next_key in tried_keys:
                    raise RuntimeError(error_message(error)) from None
                key_index, model_index = next_key, 0
                continue

            next_key = key_index
            next_model = model_index + 1
            if next_model == model_count:
                next_key = (key_index + 1) % key_count
                next_model = 0
            if next_key in blocked_keys or (next_key, next_model) in attempted_pairs:
                raise RuntimeError(error_message(error)) from None
            if is_cancelled is not None and is_cancelled():
                raise RuntimeError(present_error("Transcription was cancelled."))
            key_index, model_index = next_key, next_model
            sleep(0.5)
            continue

        return transcription, key_index, model_index

