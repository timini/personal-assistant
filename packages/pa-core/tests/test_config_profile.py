"""Tests for user profile functions in pa_core.config."""

import yaml
from unittest.mock import patch

from pa_core.config import get_user_profile, get_profile_field, set_profile_field


class TestGetUserProfile:
    @patch("pa_core.config.get_user_config")
    def test_returns_profile_dict(self, mock_config):
        mock_config.return_value = {
            "name": "Tim",
            "profile": {"address": "123 Test St", "phone": "07777"},
        }
        result = get_user_profile()
        assert result == {"address": "123 Test St", "phone": "07777"}

    @patch("pa_core.config.get_user_config")
    def test_returns_empty_dict_when_no_profile(self, mock_config):
        mock_config.return_value = {"name": "Tim"}
        result = get_user_profile()
        assert result == {}


class TestGetProfileField:
    @patch("pa_core.config.get_user_config")
    def test_returns_field_value(self, mock_config):
        mock_config.return_value = {
            "profile": {"address": "123 Test St"},
        }
        assert get_profile_field("address") == "123 Test St"

    @patch("pa_core.config.get_user_config")
    def test_returns_none_for_missing_field(self, mock_config):
        mock_config.return_value = {"profile": {"address": "123 Test St"}}
        assert get_profile_field("phone") is None

    @patch("pa_core.config.get_user_config")
    def test_returns_none_when_no_profile_section(self, mock_config):
        mock_config.return_value = {"name": "Tim"}
        assert get_profile_field("address") is None


class TestSetProfileField:
    def test_writes_field_to_yaml(self, tmp_path):
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text(yaml.dump({"name": "Tim", "timezone": "Europe/London"}))

        with patch("pa_core.config.PA_ROOT", tmp_path):
            set_profile_field("address", "123 Test St")

        data = yaml.safe_load(user_yaml.read_text())
        assert data["profile"]["address"] == "123 Test St"

    def test_preserves_existing_config(self, tmp_path):
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text(yaml.dump({"name": "Tim", "timezone": "Europe/London"}))

        with patch("pa_core.config.PA_ROOT", tmp_path):
            set_profile_field("phone", "07777")

        data = yaml.safe_load(user_yaml.read_text())
        assert data["name"] == "Tim"
        assert data["timezone"] == "Europe/London"
        assert data["profile"]["phone"] == "07777"

    def test_preserves_existing_profile_fields(self, tmp_path):
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text(
            yaml.dump({"name": "Tim", "profile": {"address": "123 Test St"}})
        )

        with patch("pa_core.config.PA_ROOT", tmp_path):
            set_profile_field("phone", "07777")

        data = yaml.safe_load(user_yaml.read_text())
        assert data["profile"]["address"] == "123 Test St"
        assert data["profile"]["phone"] == "07777"

    def test_overwrites_existing_field(self, tmp_path):
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text(
            yaml.dump({"name": "Tim", "profile": {"address": "old"}})
        )

        with patch("pa_core.config.PA_ROOT", tmp_path):
            set_profile_field("address", "new address")

        data = yaml.safe_load(user_yaml.read_text())
        assert data["profile"]["address"] == "new address"
