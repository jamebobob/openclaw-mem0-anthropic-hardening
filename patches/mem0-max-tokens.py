#!/usr/bin/env python3
"""
Patch mem0ai dist to increase AnthropicLLM max_tokens from 4096 to 8192.

Problem: The hardcoded max_tokens: 4096 in AnthropicLLM.generateResponse
causes truncated JSON responses when the memory actions update prompt is
large (many existing memories to compare). This triggers "Failed to parse
memory actions from LLM response: Unexpected end of JSON input".

This is the same class of bug as Mintplex-Labs/anything-llm#5039, where
the hardcoded 4096 limit was set for older Anthropic models and never
updated for newer models with higher output capacity.

Fix: Increase to 8192. The extraction call (~50-200 tokens output) won't
use the extra headroom. The memory actions call needs it. Cost impact is
zero (Anthropic bills actual output tokens, not max_tokens).

Location: dist/oss/index.mjs line ~277 in AnthropicLLM.generateResponse()

Written by Eve (the target OpenClaw agent) after diagnosing the issue in
live gateway logs. Self-audited: confirmed exactly 1 match, AnthropicLLM
only, no other LLM classes affected.

WARNING:
  This patches node_modules. Will be overwritten by plugin updates. Reapply.
  Run verify-patches.py after updates to check.

Usage:
  python3 mem0-max-tokens.py          # dry run (shows diff)
  python3 mem0-max-tokens.py --apply  # applies the patch

Rollback:
  cp <printed_backup_path> ~/.openclaw/extensions/openclaw-mem0/node_modules/mem0ai/dist/oss/index.mjs
"""

import os
import shutil
import sys
from datetime import datetime

DIST_PATH = os.path.expanduser(
    '~/.openclaw/extensions/openclaw-mem0/node_modules/mem0ai/dist/oss/index.mjs'
)

OLD = 'max_tokens: 4096'
NEW = 'max_tokens: 8192'

dry_run = '--apply' not in sys.argv

with open(DIST_PATH) as f:
    content = f.read()

count = content.count(OLD)

if count == 0:
    print(f"ERROR: '{OLD}' not found in {DIST_PATH}")
    print('Already patched, or dist file has changed.')
    sys.exit(1)

if count > 1:
    print(f"WARNING: Found {count} occurrences of '{OLD}'.")
    print('Expected exactly 1 (AnthropicLLM.generateResponse).')
    print('Patching ALL occurrences. Verify this is correct.')

# Show context around each match
lines = content.split('\n')
for i, line in enumerate(lines):
    if OLD in line:
        print(f'\nMatch at line {i + 1}:')
        for j in range(max(0, i - 2), min(len(lines), i + 3)):
            marker = '>>>' if j == i else '   '
            print(f'  {marker} L{j + 1}: {lines[j].rstrip()[:100]}')

if dry_run:
    print(f"\nDRY RUN: Would replace {count} occurrence(s) of '{OLD}' with '{NEW}'")
    print('Re-run with --apply to patch.')
    sys.exit(0)

# Backup
backup = f'{DIST_PATH}.bak-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
shutil.copy2(DIST_PATH, backup)
print(f'\nBackup: {backup}')

# Patch
new_content = content.replace(OLD, NEW)

# Atomic write
tmp = DIST_PATH + '.tmp'
with open(tmp, 'w') as f:
    f.write(new_content)
shutil.copystat(DIST_PATH, tmp)
os.rename(tmp, DIST_PATH)

print(f'Patched: {OLD} -> {NEW} ({count} occurrence(s))')
print(f'\nRollback: cp {backup} {DIST_PATH}')
