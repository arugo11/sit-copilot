# Mock Azure OpenAI

Azure OpenAI API のモック作成を標準化するスキル。

## When to Use

- テストで Azure OpenAI API (`openai>=1.0`) をモックする必要がある時
- `urllib.request.urlopen` を使用した関数のテスト
- `asyncio.to_thread()` 内で HTTP リクエストを行うサービスのテスト

## Trigger Phrases

- "Azure OpenAI をモックしたい"
- "テストで API 呼び出しをスタブ化"
- "LLM のレスポンスを固定したい"
- "モックパターンを適用"

## Pattern

### Helper Function

```python
from unittest.mock import patch, MagicMock
import json
from io import BytesIO

def _create_mock_http_response(data: dict, status: int = 200) -> MagicMock:
    """Create mock HTTP response object for urlopen.

    Azure OpenAI SDK uses urllib.request.urlopen internally.
    This helper creates a mock response object with the expected interface.
    """
    mock_response = MagicMock()

    # Set status code
    mock_response.status = status
    mock_response.getcode.return_value = status

    # Set headers
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.info.return_value = mock_response.headers

    # Set body
    body = json.dumps(data).encode("utf-8")
    mock_response.read.return_value = body
    mock_response.__enter__.return_value = mock_response

    return mock_response
```

### Usage Examples

#### Azure OpenAI Chat Completion Mock

```python
from unittest.mock import patch
import pytest

@patch("app.services.answerer.urlopen")
def test_generate_answer_with_azure_openai(mock_urlopen):
    # Arrange: Mock Azure OpenAI chat completion response
    mock_urlopen.return_value = _create_mock_http_response({
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a test answer from Azure OpenAI."
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    })

    # Act
    service = LectureAnswererService()
    result = await service.generate_answer(question="What is X?", context=["Source 1"])

    # Assert
    assert result.answer == "This is a test answer from Azure OpenAI."
    assert mock_urlopen.call_count == 1
```

#### Streaming Response Mock

```python
@patch("app.services.answerer.urlopen")
def test_generate_answer_with_streaming(mock_urlopen):
    # For streaming, mock multiple reads
    chunks = [
        b'{"choices": [{"delta": {"content": "Hello"}}]}',
        b'{"choices": [{"delta": {"content": " world"}}]}',
        b'[DONE]'
    ]

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.getcode.return_value = 200
    mock_response.headers = {"Content-Type": "text/event-stream"}
    mock_response.read.side_effect = chunks
    mock_response.__enter__.return_value = mock_response

    mock_urlopen.return_value = mock_response

    # Test streaming logic
```

#### Error Response Mock

```python
@patch("app.services.answerer.urlopen")
def test_generate_answer_with_api_error(mock_urlopen):
    # Arrange: Mock Azure OpenAI error response
    mock_urlopen.return_value = _create_mock_http_response({
        "error": {
            "message": "Invalid API key",
            "type": "invalid_request_error",
            "param": None,
            "code": "invalid_api_key"
        }
    }, status=401)

    # Act & Assert
    with pytest.raises(APIError, match="Invalid API key"):
        await service.generate_answer(question="Test", context=[])
```

### Async Service Pattern

サービスが `asyncio.to_thread()` を使用している場合:

```python
from unittest.mock import patch, AsyncMock

@patch("app.services.answerer.urlopen")  # Patch sync function
async def test_async_service_with_mock(mock_urlopen):
    """Test async service that uses asyncio.to_thread(urlopen, ...)"""
    mock_urlopen.return_value = _create_mock_http_response({
        "choices": [{"message": {"content": "Async response"}}]
    })

    service = LectureAnswererService()
    result = await service.generate_answer_async("question")

    assert result == "Async response"
```

## Key Points

1. **Patch Target**: `urllib.request.urlopen` をパッチする
   - Azure OpenAI SDK (openai>=1.0) は内部的に urllib を使用
   - `asyncio.to_thread()` で囲んでいても、パッチ対象は同期の `urlopen`

2. **Response Structure**: HTTP レスポンスオブジェクトのモックが必要
   - `status` / `getcode()`: ステータスコード
   - `headers` / `info()`: ヘッダー
   - `read()`: レスポンスボディ (JSON bytes)
   - `__enter__()`: コンテキストマネージャ対応

3. **Reusable Helper**: `_create_mock_http_response()` を各テストファイルに定義
   - テストファイル内のローカル関数として定義
   - conftest.py に fixture として定義しても可

4. **Verification**: 呼び出し検証を忘れずに
   - `mock_urlopen.call_count` で呼び出し回数
   - `mock_urlopen.call_args` でリクエスト内容確認

## Common Azure OpenAI Response Formats

### Chat Completion

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Response text here"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### Embedding

```json
{
  "object": "list",
  "data": [{
    "object": "embedding",
    "embedding": [0.1, 0.2, 0.3, ...],
    "index": 0
  }],
  "model": "text-embedding-ada-002",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  }
}
```

## Testing Checklist

- [ ] `_create_mock_http_response()` ヘルパー関数を定義
- [ ] 正常系（200 OK）のテスト
- [ ] 異常系（4xx, 5xx）のテスト
- [ ] 呼び出し回数・引数の検証
- [ ] ストリーミング対応の場合は複数チャンクのテスト
