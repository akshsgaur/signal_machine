"""Helpers for deriving per-user runtime tool plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agents.prompts import (
    BEHAVIORAL_AGENT_PROMPT,
    CONFLUENCE_AGENT_PROMPT,
    EXECUTION_AGENT_PROMPT,
    FEATURE_AGENT_PROMPT,
    JIRA_AGENT_PROMPT,
    SUPPORT_AGENT_PROMPT,
)


@dataclass(frozen=True)
class ResearchAgentSpec:
    agent_key: str
    provider_id: str
    prompt_template: str


PIPELINE_RESEARCH_SPECS: tuple[ResearchAgentSpec, ...] = (
    ResearchAgentSpec(
        agent_key="behavioral",
        provider_id="amplitude",
        prompt_template=BEHAVIORAL_AGENT_PROMPT,
    ),
    ResearchAgentSpec(
        agent_key="support",
        provider_id="zendesk",
        prompt_template=SUPPORT_AGENT_PROMPT,
    ),
    ResearchAgentSpec(
        agent_key="feature",
        provider_id="productboard",
        prompt_template=FEATURE_AGENT_PROMPT,
    ),
    ResearchAgentSpec(
        agent_key="execution",
        provider_id="linear",
        prompt_template=EXECUTION_AGENT_PROMPT,
    ),
    ResearchAgentSpec(
        agent_key="jira",
        provider_id="atlassian",
        prompt_template=JIRA_AGENT_PROMPT,
    ),
    ResearchAgentSpec(
        agent_key="confluence",
        provider_id="atlassian",
        prompt_template=CONFLUENCE_AGENT_PROMPT,
    ),
)


def build_pipeline_research_config(
    credentials: dict[str, dict[str, str]],
    hypothesis: str,
    product_area: str,
) -> dict[str, tuple[Callable | None, str]]:
    """Return only the research agents backed by authenticated runtime integrations."""
    fmt = {"hypothesis": hypothesis, "product_area": product_area}
    research_config: dict[str, tuple[Callable | None, str]] = {}

    for spec in PIPELINE_RESEARCH_SPECS:
        provider_credentials = credentials.get(spec.provider_id)
        if not provider_credentials:
            continue

        def _client_builder(
            provider_id: str = spec.provider_id,
            runtime_credentials: dict[str, str] = provider_credentials,
        ):
            from integrations.connections import create_mcp_client

            return create_mcp_client(provider_id, runtime_credentials)

        research_config[spec.agent_key] = (
            _client_builder,
            spec.prompt_template.format(**fmt),
        )

    return research_config
