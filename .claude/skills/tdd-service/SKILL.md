# TDD Service

サービス実装におけるテストファースト開発パターン。

## When to Use

- 新しいサービスを作成する時
- サービスのテストカバレッジを目標値（80%+）にする必要がある時
- 既存サービスのリファクタリング時

## Trigger Phrases

- "新しいサービスを作成"
- "テストファーストで実装"
- "TDD でサービス開発"
- "カバレッジを上げたい"
- "サービスのテストを追加"

## Pattern

### 1. Service Structure (Protocol First)

```python
# app/services/my_service.py

from typing import Protocol

class MyService(Protocol):
    """Service interface/contract."""

    async def execute(self, input_data: str) -> dict:
        """Execute service logic.

        Args:
            input_data: Input data for processing

        Returns:
            Processed result as dictionary
        """
        ...


class MyServiceImpl:
    """Concrete implementation of MyService."""

    def __init__(self, dependency: SomeDependency):
        self._dependency = dependency

    async def execute(self, input_data: str) -> dict:
        if not input_data:
            raise ValueError("input_data cannot be empty")

        result = await self._dependency.process(input_data)
        return {"result": result}
```

### 2. Test File Structure

```python
# tests/unit/services/test_my_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.my_service import MyServiceImpl


class TestMyServiceExecute:
    """Test suite for MyService.execute."""

    @pytest.fixture
    def mock_dependency(self):
        """Create mock dependency."""
        dep = MagicMock()
        dep.process = AsyncMock(return_value="processed")
        return dep

    @pytest.fixture
    def service(self, mock_dependency):
        """Create service instance with mocked dependencies."""
        return MyServiceImpl(mock_dependency)

    # Happy path
    async def test_execute_with_valid_input_returns_result(self, service, mock_dependency):
        # Arrange
        input_data = "test input"

        # Act
        result = await service.execute(input_data)

        # Assert
        assert result == {"result": "processed"}
        mock_dependency.process.assert_called_once_with("test input")

    # Boundary values
    @pytest.mark.parametrize("input_data", ["", " ", "a", "a" * 1000])
    async def test_execute_with_boundary_inputs(self, service, input_data):
        # Arrange
        # Act & Assert
        if not input_data.strip():
            with pytest.raises(ValueError):
                await service.execute(input_data)
        else:
            result = await service.execute(input_data)
            assert result is not None

    # Error cases
    async def test_execute_with_empty_input_raises_error(self, service):
        # Arrange
        input_data = ""

        # Act & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            await service.execute(input_data)

    # External dependency failures
    async def test_execute_when_dependency_fails_propagates_error(self, service, mock_dependency):
        # Arrange
        mock_dependency.process.side_effect = ConnectionError("DB unavailable")

        # Act & Assert
        with pytest.raises(ConnectionError, match="DB unavailable"):
            await service.execute("input")
```

### 3. Workflow

```bash
# Step 1: Create service module (with Protocol/interface)
uv run touch app/services/my_service.py

# Step 2: Create test file
uv run touch tests/unit/services/test_my_service.py

# Step 3: Write tests FIRST (TDD)
# - Define test class
# - Add fixtures
# - Write happy path test
# - Write error case tests
# - Write boundary/edge case tests

# Step 4: Implement service to make tests pass
# - Run tests: uv run pytest tests/unit/services/test_my_service.py -v
# - Implement until green

# Step 5: Verify coverage
uv run pytest --cov=app.services.my_service --cov-report=term-missing

# Step 6: Add tests for uncovered lines until 80%+
```

## Key Points

### Test Organization

1. **Test Class per Method**: `Test{MethodName}`
   - 関連するテストをグループ化
   - クラス単位で fixture 共有

2. **Descriptive Names**: `test_{method}_{condition}_{expected}`
   - テスト名から何をテストしているか一目でわかる

3. **AAA Pattern**: Arrange, Act, Assert
   - Arrange: 入力データ、モックの設定
   - Act: テスト対象メソッド実行
   - Assert: 期待値の検証

### Fixtures Best Practices

```python
# tests/conftest.py (for shared fixtures)
@pytest.fixture
def mock_azure_openai():
    """Shared mock for Azure OpenAI."""
    with patch("app.services.my_service.urlopen") as mock:
        yield mock

# tests/unit/services/test_my_service.py (for service-specific fixtures)
@pytest.fixture
def service(mock_azure_openai):
    """Create service with mocked dependencies."""
    return MyServiceImpl(deps=mock_azure_openai)
```

### Mocking Guidelines

| Dependency | Mock Strategy |
|------------|--------------|
| Database (AsyncSession) | `AsyncMock` or in-memory SQLite |
| Azure OpenAI | Mock `urllib.request.urlopen` |
| External API | `AsyncMock` for `aiohttp.ClientSession` |
| File I/O | `tmp_path` fixture or `patch` builtins |

### Coverage Targets

| Component | Target |
|-----------|--------|
| Service methods | 80%+ |
| Error handling paths | 100% |
| Public API | 100% |
| Private helpers | 70%+ |

### Red-Green-Refactor Cycle

```
1. RED: 失敗するテストを書く
   uv run pytest -x  # Stop on first failure

2. GREEN: 最小限の実装でテストを通す
   # 実装を書く

3. REFACTOR: コードを整理
   uv run ruff check .
   uv run ty check
   uv run pytest
```

## Common Test Patterns

### Async Service Test

```python
@pytest.mark.asyncio
async def test_async_service_method(self):
    # Arrange
    service = MyService()
    mock = AsyncMock(return_value="result")

    # Act
    result = await service.async_method(mock)

    # Assert
    assert result == "result"
```

### Parametrized Test

```python
@pytest.mark.parametrize("input,expected", [
    ("valid", True),
    ("", False),
    ("   ", False),
])
async def test_validate_input(self, service, input, expected):
    result = service.validate(input)
    assert result is expected
```

### Exception Testing

```python
async def test_raises_specific_error(self, service):
    with pytest.raises(ValueError) as exc_info:
        service.invalid_operation()
    assert "specific message" in str(exc_info.value)
```

## Checklist

- [ ] Protocol/Interface を定義
- [ ] テストファイルを作成
- [ ] Happy path テストを書く
- [ ] Error case テストを書く
- [ ] Boundary/edge case テストを書く
- [ ] 実装してテストを通す
- [ ] カバレッジ 80%+ を確認
- [ ] `ruff check` & `ty check` をパス
