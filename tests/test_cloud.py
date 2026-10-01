import json
from dataclasses import replace

import httpx
import pytest

from emobot.providers import Cloud, ProviderError


def cloud_with(settings, handler):
    provider = Cloud(replace(settings, api_key="test-only", api_url="http://localhost:9999/v1"))
    provider.http.close()
    provider.http = httpx.Client(transport=httpx.MockTransport(handler))
    return provider


def test_chat_http_payload(settings):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "valid"}}]})

    provider = cloud_with(settings, handler)
    try:
        assert provider.complete([{"role": "user", "content": "hello"}]) == "valid"
        body = json.loads(seen[0].content)
        assert body["model"] == settings.fast_model and body["stream"] is False
        assert seen[0].url.path == "/v1/chat/completions"
        assert seen[0].headers["Authorization"] == "Bearer test-only"
    finally:
        provider.close()


def test_multipart_transcription_and_binary_synthesis(settings, tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("transcriptions"):
            return httpx.Response(200, json={"text": "hello"})
        return httpx.Response(200, content=b"mp3data")

    provider = cloud_with(settings, handler)
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"RIFFfake")
    try:
        assert provider.transcribe(audio) == "hello"
        assert b'filename="input.wav"' in requests[0].content
        assert b"whisper-1" in requests[0].content
        assert provider.synthesize("hi") == b"mp3data"
    finally:
        provider.close()


def test_server_error_never_exposes_token(settings):
    provider = cloud_with(settings, lambda _request: httpx.Response(403, text="test-only secret"))
    try:
        with pytest.raises(ProviderError, match="HTTP 403") as error:
            provider.complete([])
        assert "test-only" not in str(error.value)
    finally:
        provider.close()
