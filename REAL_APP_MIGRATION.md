# OpportunityOS - Real App Migration

## Overview
Removed all dummy/mock components and transitioned OppurtunityOS to a real, production-ready application using only genuine AI providers.

## Changes Made

### 1. AI Provider Configuration
- **Default Provider**: Changed from "dummyai" to "openrouter"
- **Default Model**: Updated to `meta-llama/llama-3.3-70b-instruct:free` (verified free model on OpenRouter)
- **Removed**: DummyAIProvider completely from codebase

### 2. Fallback Chain (Real Providers Only)
All components now use the fallback chain:
```
OpenRouter (primary) → Groq (fallback) → Fail gracefully
```

No dummy providers in fallback chain. If both real providers fail, the application fails explicitly.

### 3. Affected Components

#### QueryGenerator (`services/search_pipeline/steps/query_generator.py`)
- Removed DummyAI from fallback order
- Now tries: OpenRouter → Groq → error
- Raises explicit error if both providers unavailable

#### OpportunityScorer (`services/opportunity_scorer/scorer.py`)
- Removed DummyAI fallback
- Now tries: OpenRouter/requested → Groq → error
- No silent fallback to dummy scores

#### AIRankingStep (`services/search_pipeline/steps/ranking.py`)
- Removed fallback scoring mechanism
- Now propagates provider errors directly
- No keyword-based fallback scoring

#### AIRegistry (`services/ai/registry.py`)
- Removed DummyAIProvider registration
- Registers only: OpenRouter, Groq
- Removed from all exports

### 4. Configuration Updates

**`core/config/settings.py`**
- `default_provider`: "dummyai" → "openrouter"
- `default_model`: "dummy-model" → "meta-llama/llama-3.3-70b-instruct:free"
- `pipeline_search_provider`: "dummy" → "tavily"

**`services/ai/__init__.py`**
- Removed DummyAIProvider import and export

**`services/__init__.py`**
- Removed DummyAIProvider from imports and exports

### 5. API Key Requirements

For the application to work, users must provide:
- **OpenRouter**: Set `OOS_AI__OPENROUTER_API_KEY` environment variable
- **Groq**: Set `OOS_AI__GROQ_API_KEY` environment variable  
- **Tavily**: Set `OOS_TAVILY__API_KEY` for search functionality

Without these, the application will fail with clear error messages indicating which providers are unavailable.

## Testing

Tests need to be updated:
- Tests using "dummy" search provider will now fail
- Integration tests require real API keys or should be mocked
- Unit tests should mock actual provider responses

## Production Readiness

✅ **Real Providers Only** - No mock/dummy components in production code
✅ **Explicit Error Handling** - Failures are clear and actionable
✅ **Configuration-Driven** - Easy to switch providers via environment variables
✅ **Fallback Chain** - Groq as automatic fallback for OpenRouter

## Migration Checklist

- [x] Remove DummyAI provider
- [x] Update config defaults to real providers
- [x] Update fallback chains in all components
- [x] Remove exports and imports
- [x] Update documentation
- [ ] Update tests to use real API keys or mocking
- [ ] Deploy with environment variables set

## Error Messages

Users will now see explicit errors when providers are unavailable:
```
No AI provider available. Requested: openrouter, Available: []
AI provider 'openrouter' failed with: ... Fallback Groq also failed: ...
```

This helps operators quickly identify when API keys are missing or credentials are invalid.
