"""测试 DeepSeekLLM — chat() 重试、错误分类、流式输出。"""

from unittest.mock import MagicMock, patch

import pytest

from src.config import LLMConfig
from src.llm.base import (
    AuthenticationError,
    LLMError,
    LLMResponse,
    LLMTimeoutError,
    RateLimitError,
)
from src.llm.deepseek_llm import DeepSeekLLM


@pytest.fixture
def llm_config():
    return LLMConfig(
        api_key="sk-test-key",
        base_url="https://api.test.com/v1",
        model="test-model",
        temperature=0.3,
        max_tokens=4096,
        timeout=30,
    )


def _make_mock_response(
    content="Hello",
    model="test-model",
    prompt_tokens=10,
    completion_tokens=5,
    total_tokens=15,
    finish_reason="stop",
):
    """构造一个模拟的 OpenAI API 响应对象。"""
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message = MagicMock()
    mock.choices[0].message.content = content
    mock.choices[0].finish_reason = finish_reason
    mock.model = model
    mock.usage = MagicMock()
    mock.usage.prompt_tokens = prompt_tokens
    mock.usage.completion_tokens = completion_tokens
    mock.usage.total_tokens = total_tokens
    return mock


class TestChat:
    """DeepSeekLLM.chat() 单元测试。"""

    def test_chat_success(self, llm_config):
        mock_response = _make_mock_response(content="你好！")

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = llm.chat([{"role": "user", "content": "你好"}])

        assert isinstance(result, LLMResponse)
        assert result.content == "你好！"
        assert result.model == "test-model"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 5
        assert result.usage["total_tokens"] == 15
        assert result.finish_reason == "stop"

    def test_chat_retry_then_success(self, llm_config):
        mock_response = _make_mock_response(content="成功")

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                Exception("temporary failure"),
                mock_response,
            ]
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = llm.chat([{"role": "user", "content": "test"}])

        assert result.content == "成功"
        assert mock_client.chat.completions.create.call_count == 2

    def test_chat_retry_exhausted_authentication(self, llm_config):
        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("401 authentication failed")
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            with pytest.raises(AuthenticationError):
                llm.chat([{"role": "user", "content": "test"}])

        assert mock_client.chat.completions.create.call_count == 3

    def test_chat_retry_exhausted_rate_limit(self, llm_config):
        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("429 rate limit exceeded")
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            with pytest.raises(RateLimitError):
                llm.chat([{"role": "user", "content": "test"}])

        assert mock_client.chat.completions.create.call_count == 3

    def test_chat_retry_exhausted_timeout(self, llm_config):
        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("request timeout")
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            with pytest.raises(LLMTimeoutError):
                llm.chat([{"role": "user", "content": "test"}])

        assert mock_client.chat.completions.create.call_count == 3

    def test_chat_retry_exhausted_generic(self, llm_config):
        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("unknown internal error")
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            with pytest.raises(LLMError, match="unknown internal error"):
                llm.chat([{"role": "user", "content": "test"}])

        assert mock_client.chat.completions.create.call_count == 3

    def test_chat_missing_api_key(self):
        config = LLMConfig(api_key="", model="test-model")
        with pytest.raises(AuthenticationError, match="API Key"):
            DeepSeekLLM(config)

    def test_chat_usage_none(self, llm_config):
        mock_response = _make_mock_response(content="OK")
        mock_response.usage = None  # usage 为 None 的情况

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = llm.chat([{"role": "user", "content": "test"}])

        assert result.usage["prompt_tokens"] == 0
        assert result.usage["completion_tokens"] == 0
        assert result.usage["total_tokens"] == 0

    def test_chat_content_none(self, llm_config):
        mock_response = _make_mock_response(content=None)

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = llm.chat([{"role": "user", "content": "test"}])

        assert result.content == ""  # None 转为空字符串

    def test_chat_custom_temperature(self, llm_config):
        mock_response = _make_mock_response()

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            llm.chat([{"role": "user", "content": "test"}], temperature=0.8)

        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]["temperature"] == 0.8


class TestStreamChat:
    """DeepSeekLLM.stream_chat() 单元测试。"""

    def _make_stream_chunks(self, texts: list[str]):
        """构造模拟的流式响应 chunk 列表。"""
        chunks = []
        for text in texts:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = text
            chunks.append(chunk)
        return chunks

    def test_stream_chat_success(self, llm_config):
        chunks = self._make_stream_chunks(["你", "好", "！"])

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = iter(chunks)
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = list(llm.stream_chat([{"role": "user", "content": "你好"}]))

        assert result == ["你", "好", "！"]

    def test_stream_chat_retry_then_success(self, llm_config):
        chunks = self._make_stream_chunks(["OK"])

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                Exception("network error"),
                iter(chunks),
            ]
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = list(llm.stream_chat([{"role": "user", "content": "test"}]))

        assert result == ["OK"]
        assert mock_client.chat.completions.create.call_count == 2

    def test_stream_chat_all_retries_exhausted(self, llm_config):
        """3 次失败后，生成器产生 [错误] 标记。"""
        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("401 unauthorized")
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            # stream_chat 耗尽重试后会 yield 错误字符串然后 raise
            results = []
            with pytest.raises(AuthenticationError):
                for token in llm.stream_chat([{"role": "user", "content": "test"}]):
                    results.append(token)

        assert mock_client.chat.completions.create.call_count == 3

    def test_stream_chat_skips_empty_deltas(self, llm_config):
        chunks = self._make_stream_chunks(["A", "", "B"])
        # 第二个 chunk 的 content 为空字符串

        with patch("src.llm.deepseek_llm.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = iter(chunks)
            mock_openai.return_value = mock_client

            llm = DeepSeekLLM(llm_config)
            result = list(llm.stream_chat([{"role": "user", "content": "test"}]))

        assert result == ["A", "B"]  # 空字符串被跳过
