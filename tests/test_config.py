"""测试配置模块"""

import pytest

from src.config import (
    AppConfig,
    ConfigurationError,
    _dict_to_dataclass,
    _resolve_config_dict,
    _resolve_env_vars,
    get_config,
    get_project_root,
    reload_config,
)

# ============================================================
# 辅助：每次测试后重置单例，避免测试间泄漏
# ============================================================


@pytest.fixture(autouse=True)
def _reset_config_singleton(monkeypatch):
    """每次测试前后重置全局配置单例和 PROJECT_ROOT。"""
    import src.config as cfg

    cfg._config = None
    yield
    cfg._config = None


# ============================================================
# 已有测试
# ============================================================


def test_resolve_env_vars_basic():
    import os

    os.environ["TEST_VAR"] = "test_value"
    result = _resolve_env_vars("${TEST_VAR}")
    assert result == "test_value"


def test_resolve_env_vars_default():
    result = _resolve_env_vars("${NONEXISTENT_VAR:default_value}")
    assert result == "default_value"


def test_resolve_env_vars_no_default():
    with pytest.raises(ConfigurationError):
        _resolve_env_vars("${NONEXISTENT_VAR_NO_DEFAULT}")


def test_appconfig_defaults():
    config = AppConfig()
    assert config.project.name == "Lecture Assistant"
    assert config.asr.model == "iic/SenseVoiceSmall"
    assert config.llm.model == "deepseek-chat"


def test_get_project_root():
    root = get_project_root()
    assert (root / "src" / "config.py").exists()


# ============================================================
# 新增：YAML 加载与单例行为
# ============================================================


def test_get_config_loads_yaml(tmp_path):
    yaml_file = tmp_path / "test_config.yaml"
    yaml_file.write_text(
        """
project:
  name: 测试课程
llm:
  model: custom-model
  temperature: 0.5
""",
        encoding="utf-8",
    )

    config = reload_config(yaml_file)
    assert config.project.name == "测试课程"
    assert config.llm.model == "custom-model"
    assert config.llm.temperature == 0.5
    # 未指定的字段使用默认值
    assert config.asr.model == "iic/SenseVoiceSmall"


def test_get_config_singleton(tmp_path):
    yaml_file = tmp_path / "cfg1.yaml"
    yaml_file.write_text("project:\n  name: SingletonTest", encoding="utf-8")

    config1 = reload_config(yaml_file)
    config2 = get_config()  # 不传参数，返回单例

    assert config1 is config2
    assert config2.project.name == "SingletonTest"


def test_reload_config(tmp_path):
    yaml1 = tmp_path / "cfg_a.yaml"
    yaml1.write_text("project:\n  name: A", encoding="utf-8")
    yaml2 = tmp_path / "cfg_b.yaml"
    yaml2.write_text("project:\n  name: B", encoding="utf-8")

    config_a = reload_config(yaml1)
    assert config_a.project.name == "A"

    config_b = reload_config(yaml2)
    assert config_b.project.name == "B"
    assert config_b is not config_a


def test_get_config_file_not_found(tmp_path):
    nonexistent = tmp_path / "does_not_exist.yaml"
    with pytest.raises(ConfigurationError, match="配置文件不存在"):
        reload_config(nonexistent)


def test_get_config_empty_yaml(tmp_path):
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="配置文件为空"):
        reload_config(empty_file)


def test_dict_to_dataclass_nested():
    data = {
        "project": {"name": "NestedTest"},
        "llm": {"model": "nested-model", "temperature": 0.7},
        "asr": {"device": "cuda"},
    }
    result = _dict_to_dataclass(AppConfig, data)

    assert isinstance(result, AppConfig)
    assert result.project.name == "NestedTest"
    assert result.llm.model == "nested-model"
    assert result.llm.temperature == 0.7
    assert result.asr.device == "cuda"
    # 未传入的字段使用 dataclass 默认值
    from src.config import LLMConfig

    default_llm = LLMConfig()
    assert result.llm.api_key == default_llm.api_key


def test_resolve_config_dict_nested():
    import os

    os.environ["TEST_NESTED_KEY"] = "resolved_value"
    data = {
        "llm": {
            "model": "${TEST_NESTED_KEY}",
            "api_key": "${TEST_NESTED_KEY:fallback}",
        },
        "project": {"name": "fixed"},
    }
    resolved = _resolve_config_dict(data)

    assert resolved["llm"]["model"] == "resolved_value"
    assert resolved["llm"]["api_key"] == "resolved_value"
    assert resolved["project"]["name"] == "fixed"


def test_reload_config_resets_singleton(tmp_path):
    yaml1 = tmp_path / "first.yaml"
    yaml1.write_text("project:\n  name: First", encoding="utf-8")
    yaml2 = tmp_path / "second.yaml"
    yaml2.write_text("project:\n  name: Second", encoding="utf-8")

    c1 = reload_config(yaml1)
    c2 = reload_config(yaml2)
    c3 = get_config()

    assert c1.project.name == "First"
    assert c2.project.name == "Second"
    assert c3 is c2  # 单例指向最后一次加载的配置
