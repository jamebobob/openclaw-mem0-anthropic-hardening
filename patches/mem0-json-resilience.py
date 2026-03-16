#!/usr/bin/env python3
"""
mem0ai JSON Parse Resilience Patch v2

Fixes: "Failed to parse memory actions from LLM response: Unexpected end of JSON input"
when using Anthropic models (which ignore responseFormat { type: "json_object" }).

Problem:
  AnthropicLLM ignores responseFormat, so the model may return JSON wrapped
  in preamble text. removeCodeBlocks() only strips triple-backtick blocks.
  The plugin's own extractJson() (line ~3253) handles this correctly but is
  only used by the vector store, not by addToVectorStore's two parse sites.

Fix:
  Replace removeCodeBlocks() to also extract the first {...} JSON object
  if the stripped string isn't valid JSON. Same regex as extractJson().

WARNING:
  This patches node_modules. Will be overwritten by plugin updates. Reapply.
  Run verify-patches.py after updates to check.

Usage:
  python3 mem0-json-resilience.py
  sudo systemctl restart openclaw
"""

import os
import shutil
from datetime import datetime

TARGET = os.path.expanduser(
    '~/.openclaw/extensions/openclaw-mem0/node_modules/mem0ai/dist/oss/index.mjs'
)
BACKUP = f'{TARGET}.backup-resilience-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
TEMP = f'{TARGET}.tmp'

OLD = '''function removeCodeBlocks(text) {
  return text.replace(/```[^`]*```/g, "");
}'''

NEW = '''function removeCodeBlocks(text) {
  let cleaned = text.replace(/```[^`]*```/g, "");
  try {
    JSON.parse(cleaned);
    return cleaned;
  } catch (e) {
    const match = cleaned.match(/\\{[\\s\\S]*\\}/);
    return match ? match[0] : cleaned;
  }
}'''

# Backup
shutil.copy2(TARGET, BACKUP)
print(f'Backup: {BACKUP}')

# Read
with open(TARGET, 'r') as f:
    content = f.read()

# Verify exactly one match
count = content.count(OLD)
if count == 0:
    print('ERROR: Could not find removeCodeBlocks function.')
    print('Already patched, or plugin was updated?')
    exit(1)
if count > 1:
    print(f'ERROR: Found {count} matches. Expected exactly 1. Aborting.')
    exit(1)

# Replace
content = content.replace(OLD, NEW, 1)

# Atomic write
with open(TEMP, 'w') as f:
    f.write(content)

shutil.copystat(TARGET, TEMP)
os.rename(TEMP, TARGET)

print('Patched removeCodeBlocks() with JSON extraction fallback.')
print()
print('Before: strip backticks only')
print('After:  strip backticks -> try JSON.parse -> extract first {...} if needed')
print()
print('NOTE: This patches node_modules. Reapply after plugin updates.')
print(f'To rollback: cp {BACKUP} {TARGET}')
print('Restart: sudo systemctl restart openclaw')
