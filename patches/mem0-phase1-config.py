#!/usr/bin/env python3
"""
mem0 Phase 1 Config Patch v7

Patches openclaw.json to improve Mem0 memory extraction quality:
  1. Adds customPrompt replacing the default "Personal Information Organizer"
  2. Sets searchThreshold to 0.6 (from default 0.3)
  3. Swaps extraction LLM to Anthropic Sonnet

Prerequisite: openclaw-mem0 must be installed in open-source mode with
an existing oss.llm block in your config. This patch replaces the LLM
config; it does not create the OSS structure from scratch.

See CHANGELOG.md for the full 7-version audit trail.

Usage:
  python3 mem0-phase1-config.py
  sudo systemctl restart openclaw
"""

import json
import os
import shutil
import sys
from datetime import datetime

CONFIG_PATH = os.path.expanduser('~/.openclaw/openclaw.json')
BACKUP_PATH = f'{CONFIG_PATH}.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
TEMP_PATH = f'{CONFIG_PATH}.tmp'

# --- Preflight checks ---
if not os.path.exists(CONFIG_PATH):
    print(f'ERROR: {CONFIG_PATH} not found.')
    sys.exit(1)

with open(CONFIG_PATH) as f:
    cfg = json.load(f)

# Verify plugin config structure exists
try:
    mem0 = cfg['plugins']['entries']['openclaw-mem0']['config']
except KeyError as e:
    print(f'ERROR: Missing config path in openclaw.json: {e}')
    print('Is openclaw-mem0 installed? Expected: plugins.entries.openclaw-mem0.config')
    sys.exit(1)

if 'oss' not in mem0:
    print('ERROR: No "oss" block in openclaw-mem0 config.')
    print('This patch requires open-source mode. Expected: config.oss.llm')
    sys.exit(1)

if 'llm' not in mem0['oss']:
    print('ERROR: No "llm" block in config.oss.')
    print('This patch replaces the existing LLM config. Configure one first.')
    sys.exit(1)

# --- Backup ---
shutil.copy2(CONFIG_PATH, BACKUP_PATH)
print(f'Backup: {BACKUP_PATH}')

# --- 1. Custom extraction prompt ---
# The word "JSON" must appear in the prompt. mem0ai (index.mjs ~4647)
# checks customPrompt.toLowerCase().includes("json"):
#   - If found: uses prompt as-is for system message
#   - If not found: appends its own JSON instruction suffix
# We include "JSON" explicitly so the prompt is used verbatim.
#
# Note: default Mem0 prompt includes language detection. This prompt
# omits it (English-primary use). Add back if needed for group chats.
mem0['customPrompt'] = (
    'You are a memory curator for a personal AI assistant. '
    'Extract ONLY high-value personal facts useful in future conversations.\n\n'
    'EXTRACT:\n'
    '- Personal facts the user states (preferences, skills, location, relationships)\n'
    '- Technical decisions and project choices\n'
    '- Explicit preferences ("I prefer X", "I don\'t like Y")\n'
    '- Ongoing projects, goals, commitments\n\n'
    'DO NOT EXTRACT:\n'
    '- Greetings, thanks, acknowledgements, filler\n'
    '- Channel metadata, sender names, message IDs, timestamps\n'
    '- Anything the assistant said\n'
    '- Observations about the conversation itself\n'
    '- Summaries of what happened in the conversation\n\n'
    'Return a JSON object. Return {"facts": []} if nothing qualifies. '
    'Return {"facts": ["fact1", "fact2"]} if facts are found.\n\n'
    'Examples:\n'
    'Input: Hi, how are you?\n'
    'Output: {"facts": []}\n\n'
    'Input: [From: Alex via chat] Remember I prefer Python over Node for scripts.\n'
    'Output: {"facts": ["Prefers Python over Node.js for scripting"]}\n\n'
    'Input: The assistant helped configure the server today.\n'
    'Output: {"facts": []}'
)

# --- 2. Raise search threshold ---
mem0['searchThreshold'] = 0.6

# --- 3. Swap extraction LLM to Anthropic Sonnet ---
# ConfigManager merge (index.mjs ~3742) whitelist:
#   baseURL, apiKey, model, modelProperties
# temperature/maxTokens silently dropped, intentionally omitted.
#
# AnthropicLLM reads apiKey from config or falls back to
# process.env.ANTHROPIC_API_KEY. No key needed in config if set in env.
#
# Change "claude-sonnet-4-6" to your preferred model string.
# For lower cost, use "claude-haiku-4-5-20251001".
old_llm = json.dumps(mem0['oss']['llm'], indent=2)
mem0['oss']['llm'] = {
    'provider': 'anthropic',
    'config': {
        'model': 'claude-sonnet-4-6'
    }
}

# --- Write to temp file, preserve permissions, atomic rename ---
with open(TEMP_PATH, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')

shutil.copystat(CONFIG_PATH, TEMP_PATH)
os.rename(TEMP_PATH, CONFIG_PATH)

# --- Report ---
print()
print('Patched openclaw.json:')
print(f'  customPrompt: {len(mem0["customPrompt"])} chars')
print(f'  "json" in prompt: {"json" in mem0["customPrompt"].lower()}')
print(f'  searchThreshold: {mem0["searchThreshold"]}')
llm = mem0['oss']['llm']
print(f'  oss.llm: provider={llm["provider"]} model={llm["config"]["model"]}')
print(f'  apiKey: from process.env.ANTHROPIC_API_KEY')
print()
print(f'Old LLM config was:')
print(f'{old_llm}')
print()
print('Next steps:')
print('  1. sudo systemctl restart openclaw')
print('  2. Send a test message with a real fact: "I prefer dark mode"')
print('  3. Send filler: "hi" "thanks" "ok"')
print('  4. Check: openclaw mem0 search "dark mode" --scope long-term')
print('  5. Verify: one clean memory from the fact, zero from filler')
print()
print(f'To rollback: cp {BACKUP_PATH} {CONFIG_PATH} && sudo systemctl restart openclaw')
