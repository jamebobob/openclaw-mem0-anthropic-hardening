# openclaw-mem0-anthropic-hardening

Production hardening patches for the `@mem0/openclaw-mem0` plugin (v0.1.2) when using Anthropic models as the extraction LLM.

The official plugin works well with OpenAI models but has several silent failure modes when paired with Anthropic's API. These patches fix all of them.

## The Problem

Out of the box, `@mem0/openclaw-mem0` in open-source mode uses a generic "Personal Information Organizer" extraction prompt and defaults to whatever LLM you configure. When you swap to Anthropic (Claude Sonnet, Haiku, etc.) for extraction, three things break:

1. **Junk memories.** The default extraction prompt stores everything: greetings, metadata, filler, duplicate facts. A typical install accumulates thousands of low-value memories.

2. **Truncated JSON responses.** `AnthropicLLM` hardcodes `max_tokens: 4096`. The memory actions call (which decides ADD/UPDATE/DELETE for each extracted fact) can exceed this, producing truncated JSON and "Failed to parse memory actions" errors. This is the same class of bug as [Mintplex-Labs/anything-llm#5039](https://github.com/Mintplex-Labs/anything-llm/issues/5039), where the hardcoded 4096 limit was set for older models and never updated. Not yet reported upstream on mem0.

3. **Ignored response format.** The plugin passes `{ type: "json_object" }` to enforce JSON output, but `AnthropicLLM` silently ignores this parameter. When the model returns preamble text before JSON, the parser fails.

## What These Patches Do

### Patch 1: Config (`patches/mem0-phase1-config.py`)

- **Custom extraction prompt** replacing the default "Personal Information Organizer" with strict rules: extract only user-stated facts, preferences, decisions, and commitments. Ignore greetings, metadata, assistant output, and conversation summaries.
- **Search threshold** raised from 0.3 to 0.6, filtering low-relevance junk from recall.
- **LLM swap** to Anthropic Sonnet for extraction (configurable model string). Reads `ANTHROPIC_API_KEY` from environment automatically.

### Patch 2: JSON Resilience (`patches/mem0-json-resilience.py`)

Replaces the `removeCodeBlocks()` function to also extract the first `{...}` JSON object from responses wrapped in preamble text. Uses the same regex approach as the plugin's existing `extractJson()` function, applied to both JSON parse call sites in `addToVectorStore`.

### Patch 3: max_tokens (`patches/mem0-max-tokens.py`)

Bumps the hardcoded `max_tokens: 4096` in `AnthropicLLM.generateResponse()` to `8192`. The extraction call output is tiny (50-200 tokens), but the memory actions call can be larger when comparing against existing memories. Cost impact is zero since Anthropic bills actual output tokens, not the limit.

## Prerequisites

- Python 3 on the host machine
- SSH access to your OpenClaw server
- `ANTHROPIC_API_KEY` in your environment (systemd service file, `.env`, or shell)
- `@mem0/openclaw-mem0` plugin installed in **open-source mode** with an `oss.llm` block already configured in your `openclaw.json`. Patch 1 replaces the existing LLM config; it does not create one from scratch.
- Config path: `~/.openclaw/openclaw.json` (legacy `~/.clawdbot/` paths are auto-migrated by OpenClaw)

## Compatibility

- **OpenClaw:** v2026.3.7+ (tested on v2026.3.13)
- **Plugin:** `@mem0/openclaw-mem0` v0.1.2 (official, installed via `openclaw plugins install`)
- **LLM:** Any Anthropic model. Tested with `claude-sonnet-4-6`. Works with Haiku for lower cost.
- **Embedder:** Any (tested with ollama/nomic-embed-text). Patches do not touch the embedder.
- **Vector store:** Any (tested with Qdrant). Patches do not touch the vector store.

## Installation

Copy the patches to your server:

```
scp patches/*.py verify-patches.py youruser@yourserver:/tmp/
```

SSH in and run them in order:

```
# Patch 1: Config (backs up openclaw.json automatically)
python3 /tmp/mem0-phase1-config.py

# Patch 2: JSON resilience (backs up index.mjs automatically)
python3 /tmp/mem0-json-resilience.py

# Patch 3: max_tokens (backs up index.mjs automatically, dry-run by default)
python3 /tmp/mem0-max-tokens.py          # preview
python3 /tmp/mem0-max-tokens.py --apply  # apply

# Restart
sudo systemctl restart openclaw
```

### Verify

After installation (or after a plugin update), run:

```
python3 /tmp/verify-patches.py
```

Output shows the status of each patch:

```
Patch 1 (config):
  customPrompt: APPLIED
  searchThreshold: 0.6 APPLIED
  LLM: anthropic/claude-sonnet-4-6 APPLIED

Patch 2 (JSON resilience):
  removeCodeBlocks: APPLIED

Patch 3 (max_tokens):
  max_tokens: 8192 APPLIED

All patches applied.
```

You can also test extraction manually. Send a real fact ("I prefer dark mode") and filler ("hi", "thanks"):

```
# Check for clean extraction (no parse errors)
sudo journalctl -u openclaw --since '2 min ago' | grep -i 'mem0\|parse\|failed\|captured'
```

You should see `auto-captured 1 memories` with zero "Failed to parse" errors.

### Rollback

Each patch prints its rollback command on execution. All backups are timestamped.

**Important: Patches 2 and 3 modify the same file** (`node_modules/mem0ai/dist/oss/index.mjs`). Apply them in order (2 then 3). If you need to rollback patch 2, it will also undo patch 3. To rollback only patch 3, use the backup created by patch 3 (not patch 2's backup).

## After Plugin Updates

Patches 2 and 3 modify `node_modules` and will be overwritten by `openclaw plugins update`. Patch 1 modifies `openclaw.json` and survives updates.

After any plugin update:

```
python3 verify-patches.py
# If patches 2 or 3 show NOT APPLIED, rerun them:
python3 mem0-json-resilience.py
python3 mem0-max-tokens.py --apply
sudo systemctl restart openclaw
```

## Technical Details

These patches were developed by tracing through the plugin's TypeScript source code (compiled to `dist/oss/index.mjs`) to understand the exact behavior:

- **ConfigManager LLM merge** (line ~3742) only passes through `baseURL`, `apiKey`, `model`, and `modelProperties`. All other config keys (temperature, maxTokens, etc.) are silently dropped. This is why temperature and maxTokens cannot be set via config and why patch 3 modifies the source.
- **customPrompt handling** (line ~4647) checks if the prompt contains "json" (case-insensitive). If not found, it appends its own JSON instruction suffix. The custom prompt includes "JSON" explicitly to prevent this.
- **AnthropicLLM.generateResponse** (line ~265) accepts a `responseFormat` parameter but ignores it entirely. The `messages.create` call only passes `model`, `messages`, `system`, and `max_tokens`.
- **removeCodeBlocks** (line ~2595) is called at both JSON parse sites in `addToVectorStore` (fact extraction at line ~4660, memory actions at line ~4699) but originally only stripped backtick fences without extracting JSON.

## Audit Trail

This code went through 8 rounds of independent audit before deployment:

- 6 rounds by Claude Opus (prompt-level source code verification against the actual plugin)
- 1 round by Claude Code (automated review with file access)
- 1 round by the target agent (Eve) with runtime access to the live system

See [CHANGELOG.md](CHANGELOG.md) for what each round found.

## Related Issues

- [mem0ai/mem0#4037](https://github.com/mem0ai/mem0/issues/4037) - Auto-recall property name bug (fixed in v0.1.2)
- [mem0ai/mem0#4063](https://github.com/mem0ai/mem0/issues/4063) - Auto-capture drops content when recall context injected (fixed in v0.1.2)
- [mem0ai/mem0#4268](https://github.com/mem0ai/mem0/issues/4268) - TS SDK embedder ignores baseURL (open)
- [mem0ai/mem0#4126](https://github.com/mem0ai/mem0/issues/4126) - Per-agent plugin config not supported (open)
- [Mintplex-Labs/anything-llm#5039](https://github.com/Mintplex-Labs/anything-llm/issues/5039) - Same max_tokens: 4096 hardcode in another Anthropic provider

## Credits

Built by [@jamebobob](https://github.com/jamebobob) + Claude Opus.
max_tokens patch and runtime debugging by Eve (the target OpenClaw agent).
JSON resilience approach inspired by [1960697431/openclaw-mem0](https://github.com/1960697431/openclaw-mem0).

## License

MIT
