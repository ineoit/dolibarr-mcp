"""
Test configuration module for Dolibarr MCP Server.
"""

import os

# Import only existing modules
import sys
<<<<<<< HEAD
from unittest.mock import patch

import pytest

sys.path.insert(0, 'src')
=======

sys.path.insert(0, "src")
>>>>>>> a696eee (fix(pre-commit): black formatting)
from dolibarr_mcp.config import Config


class TestConfig:
    """Test configuration loading and validation."""

    def test_config_from_env(self):
        """Test configuration loading from environment variables."""
        with patch.dict(
            os.environ, {"DOLIBARR_URL": "https://test.dolibarr.com", "DOLIBARR_API_KEY": "test_key_123", "LOG_LEVEL": "DEBUG"}
        ):
            config = Config(
                dolibarr_url=os.getenv("DOLIBARR_URL"),
                dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"),
                log_level=os.getenv("LOG_LEVEL"),
            )
<<<<<<< HEAD
            assert config.dolibarr_url == 'https://test.dolibarr.com/api/index.php'
            assert config.dolibarr_api_key == 'test_key_123'
            assert config.log_level == 'DEBUG'
=======
            assert config.dolibarr_url == "https://test.dolibarr.com/api/index.php"
            assert config.dolibarr_api_key == "test_key_123"
            assert config.log_level == "DEBUG"
>>>>>>> a696eee (fix(pre-commit): black formatting)

    def test_config_defaults(self):
        """Test configuration defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
<<<<<<< HEAD
            assert config.log_level == 'INFO'  # Default log level
=======
            assert config.log_level == "INFO"  # Default log level
>>>>>>> a696eee (fix(pre-commit): black formatting)

    def test_config_url_normalization(self):
        """Test URL normalization (adding API path)."""
        with patch.dict(os.environ, {"DOLIBARR_URL": "https://test.dolibarr.com/", "DOLIBARR_API_KEY": "test_key"}):
            config = Config(dolibarr_url=os.getenv("DOLIBARR_URL"), dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"))
            # Should add /api/index.php
<<<<<<< HEAD
            assert config.dolibarr_url == 'https://test.dolibarr.com/api/index.php'
            assert not config.dolibarr_url.endswith('//')
=======
            assert config.dolibarr_url == "https://test.dolibarr.com/api/index.php"
            assert not config.dolibarr_url.endswith("//")
>>>>>>> a696eee (fix(pre-commit): black formatting)

    def test_config_from_dotenv(self, tmp_path):
        """Test configuration loading from .env file."""
        env_file = tmp_path / ".env"
<<<<<<< HEAD
        env_file.write_text(
            "DOLIBARR_URL=https://env.dolibarr.com\n"
            "DOLIBARR_API_KEY=env_key_456\n"
            "LOG_LEVEL=WARNING\n"
        )
=======
        env_file.write_text("DOLIBARR_URL=https://env.dolibarr.com\n" "DOLIBARR_API_KEY=env_key_456\n" "LOG_LEVEL=WARNING\n")
>>>>>>> a696eee (fix(pre-commit): black formatting)

        # Start from an empty environment: importing dolibarr_mcp.config already
        # ran load_dotenv() on the working directory, and load_dotenv() does not
        # override variables that are already set, so a local .env would win.
        with patch.dict(os.environ, {}, clear=True):
            # Load from env file
            from dotenv import load_dotenv

            load_dotenv(str(env_file))

            config = Config(
                dolibarr_url=os.getenv("DOLIBARR_URL"),
                dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"),
                log_level=os.getenv("LOG_LEVEL"),
            )
<<<<<<< HEAD
            assert config.dolibarr_url == 'https://env.dolibarr.com/api/index.php'
            assert config.dolibarr_api_key == 'env_key_456'
            assert config.log_level == 'WARNING'

    def test_config_precedence(self):
        """Test that environment variables take precedence over defaults."""
        with patch.dict(os.environ, {
            'DOLIBARR_URL': 'https://env.dolibarr.com',
            'DOLIBARR_API_KEY': 'env_key'
        }):
            config = Config(
                dolibarr_url=os.getenv('DOLIBARR_URL'),
                dolibarr_api_key=os.getenv('DOLIBARR_API_KEY')
            )
            assert config.dolibarr_url == 'https://env.dolibarr.com/api/index.php'
            assert config.dolibarr_api_key == 'env_key'

    def test_log_level_validation(self):
        """Test log level validation."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
=======
            assert config.dolibarr_url == "https://env.dolibarr.com/api/index.php"
            assert config.dolibarr_api_key == "env_key_456"
            assert config.log_level == "WARNING"

    def test_config_precedence(self):
        """Test that environment variables take precedence over defaults."""
        with patch.dict(os.environ, {"DOLIBARR_URL": "https://env.dolibarr.com", "DOLIBARR_API_KEY": "env_key"}):
            config = Config(dolibarr_url=os.getenv("DOLIBARR_URL"), dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"))
            assert config.dolibarr_url == "https://env.dolibarr.com/api/index.php"
            assert config.dolibarr_api_key == "env_key"

    def test_log_level_validation(self):
        """Test log level validation."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
>>>>>>> a696eee (fix(pre-commit): black formatting)

        for level in valid_levels:
            with patch.dict(os.environ, {"DOLIBARR_URL": "https://test.com", "DOLIBARR_API_KEY": "key", "LOG_LEVEL": level}):
                config = Config(
                    dolibarr_url=os.getenv("DOLIBARR_URL"),
                    dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"),
                    log_level=os.getenv("LOG_LEVEL"),
                )
                assert config.log_level == level

    def test_invalid_log_level(self):
        """Test invalid log level falls back to default."""
        with patch.dict(os.environ, {"DOLIBARR_URL": "https://test.com", "DOLIBARR_API_KEY": "key", "LOG_LEVEL": "INVALID"}):
            config = Config(
                dolibarr_url=os.getenv("DOLIBARR_URL"), dolibarr_api_key=os.getenv("DOLIBARR_API_KEY"), log_level="INVALID"
            )
<<<<<<< HEAD
            assert config.log_level == 'INFO'  # Should fall back to default
=======
            assert config.log_level == "INFO"  # Should fall back to default
>>>>>>> a696eee (fix(pre-commit): black formatting)

    def test_api_key_alias(self):
        """Test backward compatibility alias for api_key."""
        config = Config(dolibarr_url="https://test.com", dolibarr_api_key="test_key")
        assert config.api_key == "test_key"  # Should work via alias
