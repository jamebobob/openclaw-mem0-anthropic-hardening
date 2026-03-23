# CHANGELOG

All notable changes to these patches are documented here.

## Repo

### v2 - 2026-03-15 (current)

- **Added verify-patches.py.** One-command check for all three patches.
  Exits 0 if all applied, non-zero with details on what's missing.
  Essential after plugin updates which overwrite patches 2 and 3.
- **Added legacy path note** to README (auto-migrated by OpenClaw).
- **Added prerequisite checks** to config patch for missing config keys.
- **Added "After Plugin Updates" section** to README with reapply workflow.
- **Added Technical Details section** to README documenting the source
  code lines and behaviors each patch addresses.
- **Added cross-project reference** to anything-llm#5039 for the
  max_tokens hardcode bug (same class of issue, different project).

### v1 - 2026-03-15

- Initial GitHub release with three patches, CHANGELOG, and README.

---

## Config Patch (mem0-phase1-config.py)

### v7 - 2026-03-15 (current)

- **ensure_ascii=False** added to json.dump. Without this, non-ASCII
  characters in openclaw.json get re-encoded as \uXXXX escape sequences,
  creating churn in values the patch never intended to touch.
  Found by Claude Code audit (round 7).
- **Prerequisite checks** added. Script now validates that the plugin
  config structure exists (plugins.entries.openclaw-mem0.config.oss.llm)
  before attempting changes. Found in round 8 self-audit.

### v6 - 2026-03-15

- **Switched from Venice/Mistral to Anthropic/Sonnet.** Venice API was
  unstable. Anthropic is the primary provider, key already in systemd,
  SDK is native (no OpenAI-compatible shim needed).

### v5 - 2026-03-15

- **customPrompt missing "json" keyword.** mem0ai (index.mjs ~4647) checks
  customPrompt.toLowerCase().includes("json"). Without it, an uncontrolled
  suffix gets appended. Added "Return a JSON object." explicitly.

### v4 - 2026-03-15

- **File permissions lost on rename.** Added shutil.copystat before rename.
- **Missing trailing newline.** Added f.write('\n') after json.dump.

### v3 - 2026-03-15

- **Crash-unsafe file write.** Changed to temp file + atomic os.rename.
- **Removed dead config keys.** temperature and maxTokens silently dropped
  by ConfigManager merge whitelist (baseURL, apiKey, model, modelProperties).

### v2 - 2026-03-15

- **Wrong config key casing.** api_key/base_url (snake_case) silently
  ignored by TypeScript SDK. Fixed to apiKey/baseURL (camelCase).

### v1 - 2026-03-15

- Initial draft.

---

## JSON Resilience Patch (mem0-json-resilience.py)

### v2 - 2026-03-15 (current)

- Audit passed. Approach confirmed by community consensus across multiple
  projects dealing with Anthropic JSON extraction. No changes from v1.

### v1 - 2026-03-15

- Replaced removeCodeBlocks() with JSON extraction fallback.

---

## max_tokens Patch (mem0-max-tokens.py)

### v1 - 2026-03-15 (current)

- Written by the target agent after diagnosing truncated memory
  action responses in live gateway logs.
- Bumps AnthropicLLM.generateResponse() max_tokens from 4096 to 8192.
- Same bug class as Mintplex-Labs/anything-llm#5039 (hardcoded 4096
  for Anthropic, never updated for newer models). Not yet reported
  upstream on mem0ai.
- Dry run by default. Requires --apply flag.
