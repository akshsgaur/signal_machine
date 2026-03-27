import unittest

from agents.runtime_plan import build_pipeline_research_config


class PipelineRuntimeFilteringTests(unittest.TestCase):
    def test_only_authenticated_runtime_providers_are_included(self) -> None:
        config = build_pipeline_research_config(
            {
                "linear": {"token": "lin_api_123"},
                "productboard": {"token": "pb_123"},
            },
            hypothesis="Users need faster triage",
            product_area="issue triage",
        )

        self.assertEqual(sorted(config.keys()), ["execution", "feature"])

    def test_atlassian_enables_both_jira_and_confluence_agents(self) -> None:
        config = build_pipeline_research_config(
            {
                "atlassian": {
                    "url": "https://example.atlassian.net",
                    "username": "pm@example.com",
                    "api_token": "jira-token",
                }
            },
            hypothesis="Docs are blocking launches",
            product_area="release process",
        )

        self.assertEqual(sorted(config.keys()), ["confluence", "jira"])

    def test_connect_only_airbyte_provider_does_not_create_runtime_agent(self) -> None:
        config = build_pipeline_research_config(
            {
                "github": {"token": "ghp_123"},
            },
            hypothesis="PR throughput is slowing releases",
            product_area="engineering workflow",
        )

        self.assertEqual(config, {})


if __name__ == "__main__":
    unittest.main()
