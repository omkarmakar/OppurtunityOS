"""Dummy AI provider for development and testing."""

from __future__ import annotations

from services.ai.models import AIResponse, ModelConfig
from services.ai.provider import AIProvider


class DummyAIProvider(AIProvider):
    @property
    def name(self) -> str:
        return "DummyAI"

    @property
    def supported_models(self) -> list[str]:
        return ["dummy-model"]

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: ModelConfig | None = None,
    ) -> AIResponse:
        cfg = config or ModelConfig()
        last = messages[-1]["content"] if messages else ""
        
        # Return a valid JSON array for query generation requests
        if "Generate" in last and "search queries" in last:
            return AIResponse(
                content='["software engineer remote", "python developer", "full stack engineer", "backend developer", "web developer"]',
                model=cfg.model,
                provider=self.name,
                usage={"prompt_tokens": 10, "completion_tokens": 5},
                finish_reason="stop",
            )
        
        # Return valid JSON scoring response for opportunity scoring
        if "Score this opportunity" in last or "User Profile:" in last:
            return AIResponse(
                content='''{
  "relevance_score": 75,
  "summary": "Strong match for the user's skills and experience",
  "pros": ["Remote position", "Good salary range", "Growth opportunities"],
  "cons": ["Requires relocation after 6 months"],
  "required_skills": ["Python", "FastAPI", "Docker"],
  "missing_skills": ["Kubernetes"],
  "application_deadline": "2025-02-28",
  "ranking_explanation": "This opportunity aligns well with the user's technical background and preferred work style"
}''',
                model=cfg.model,
                provider=self.name,
                usage={"prompt_tokens": 100, "completion_tokens": 50},
                finish_reason="stop",
            )
        
        return AIResponse(
            content=f"Echo: {last}",
            model=cfg.model,
            provider=self.name,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
        )
