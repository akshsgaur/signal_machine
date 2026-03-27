import os
import unittest
from unittest.mock import patch

from integrations.airbyte import build_airbyte_credentials, get_airbyte_definition_id
from integrations.registry import build_integration_status_map, get_provider, is_provider_connectable


class AirbyteIntegrationTests(unittest.TestCase):
    def test_linear_credentials_map_to_airbyte_shape(self) -> None:
        self.assertEqual(
            build_airbyte_credentials("linear", {"token": "lin_api_123"}),
            {"api_key": "lin_api_123"},
        )

    def test_monday_credentials_map_to_airbyte_shape(self) -> None:
        self.assertEqual(
            build_airbyte_credentials("monday", {"api_token": "monday-token"}),
            {"api_key": "monday-token"},
        )

    def test_additional_token_connectors_map_to_airbyte_shapes(self) -> None:
        self.assertEqual(
            build_airbyte_credentials("asana", {"token": "asana-token"}),
            {"token": "asana-token"},
        )
        self.assertEqual(
            build_airbyte_credentials("github", {"token": "ghp_token"}),
            {"token": "ghp_token"},
        )
        self.assertEqual(
            build_airbyte_credentials("sentry", {"auth_token": "sentry-token"}),
            {"auth_token": "sentry-token"},
        )
        self.assertEqual(
            build_airbyte_credentials("typeform", {"access_token": "tf-token"}),
            {"access_token": "tf-token"},
        )

    def test_unsupported_provider_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_airbyte_credentials("amplitude", {"api_key": "abc"})

    def test_airbyte_provider_requires_env_configuration(self) -> None:
        provider = get_provider("linear")
        self.assertIsNotNone(provider)
        assert provider is not None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AIRBYTE_CLIENT_ID", None)
            os.environ.pop("AIRBYTE_CLIENT_SECRET", None)
            os.environ.pop("AIRBYTE_ORGANIZATION_ID", None)
            self.assertFalse(is_provider_connectable(provider))

        with patch.dict(
            os.environ,
            {
                "AIRBYTE_CLIENT_ID": "client-id",
                "AIRBYTE_CLIENT_SECRET": "client-secret",
                "AIRBYTE_ORGANIZATION_ID": "org-id",
            },
            clear=False,
        ):
            self.assertTrue(is_provider_connectable(provider))

    def test_definition_ids_are_internalized(self) -> None:
        self.assertEqual(get_airbyte_definition_id("linear"), "1c5d8316-ed42-4473-8fbc-2626f03f070c")
        self.assertEqual(get_airbyte_definition_id("github"), "ef69ef6e-aa7f-4af1-a01d-ef775033524e")
        self.assertIsNone(get_airbyte_definition_id("amplitude"))

    def test_status_map_exposes_airbyte_runtime_flags(self) -> None:
        statuses = build_integration_status_map({"linear"})
        self.assertIn("linear", statuses)
        self.assertEqual(statuses["linear"]["provider_backend"], "airbyte_cloud")
        self.assertTrue(statuses["linear"]["runtime_ready"])

    def test_workspace_scoped_macroscope_status_is_derived_from_workspace_connections(self) -> None:
        statuses = build_integration_status_map(set(), {"macroscope"})
        self.assertIn("macroscope", statuses)
        self.assertTrue(statuses["macroscope"]["connected"])
        self.assertEqual(statuses["macroscope"]["connection_scope"], "workspace")

    def test_new_airbyte_catalog_entries_are_connect_only(self) -> None:
        linear = get_provider("linear")
        github = get_provider("github")
        asana = get_provider("asana")
        sentry = get_provider("sentry")
        typeform = get_provider("typeform")
        self.assertIsNotNone(linear)
        assert linear is not None
        self.assertEqual(linear.provider_backend, "airbyte_cloud")
        self.assertTrue(linear.runtime_ready)
        self.assertEqual(linear.builder_key, "linear")
        for provider in (github, asana, sentry, typeform):
            self.assertIsNotNone(provider)
            assert provider is not None
            self.assertEqual(provider.provider_backend, "airbyte_cloud")
            self.assertEqual(provider.surfaces, ["connect"])
            self.assertFalse(provider.runtime_ready)
            self.assertIsNotNone(provider.airbyte_provider_name)

    def test_macroscope_is_workspace_scoped_engineering_source(self) -> None:
        provider = get_provider("macroscope")
        self.assertIsNotNone(provider)
        assert provider is not None
        self.assertEqual(provider.category, "Engineering Intelligence")
        self.assertEqual(provider.connection_scope, "workspace")
        self.assertEqual(provider.connection_mode, "inline_credentials")
        self.assertEqual(provider.auth_mode, "json_credentials")
        self.assertIn("chat", provider.surfaces)
        self.assertIn("pipeline", provider.surfaces)


if __name__ == "__main__":
    unittest.main()
