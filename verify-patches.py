#!/usr/bin/env python3
"""
Verify all three mem0 anthropic hardening patches are applied.

Run after plugin updates to check if patches 2 and 3 need reapplying.
Exit code 0 = all patches applied. Non-zero = something needs attention.

Usage:
  python3 verify-patches.py
"""

import json
import os
import sys

CONFIG_PATH = os.path.expanduser('~/.openclaw/openclaw.json')
DIST_PATH = os.path.expanduser(
    '~/.openclaw/extensions/openclaw-mem0/node_modules/mem0ai/dist/oss/index.mjs'
)

ok = True

# --- Patch 1: Config ---
print('Patch 1 (config):')
try:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    mem0 = cfg['plugins']['entries']['openclaw-mem0']['config']

    cp = mem0.get('customPrompt', '')
    if 'memory curator' in cp and 'json' in cp.lower():
        print('  customPrompt: APPLIED')
    else:
        print('  customPrompt: MISSING or default')
        ok = False

    st = mem0.get('searchThreshold')
    if st and st >= 0.5:
        print(f'  searchThreshold: {st} APPLIED')
    else:
        print(f'  searchThreshold: {st} (default or low)')
        ok = False

    llm = mem0.get('oss', {}).get('llm', {})
    if llm.get('provider') == 'anthropic':
        print(f'  LLM: anthropic/{llm.get("config", {}).get("model", "?")} APPLIED')
    else:
        print(f'  LLM: {llm.get("provider", "?")} (not anthropic)')
        ok = False

except Exception as e:
    print(f'  ERROR reading config: {e}')
    ok = False

# --- Read dist file once for patches 2 and 3 ---
dist = None
try:
    with open(DIST_PATH) as f:
        dist = f.read()
except FileNotFoundError:
    pass

# --- Patch 2: JSON resilience ---
print('\nPatch 2 (JSON resilience):')
if dist is None:
    print(f'  ERROR: {DIST_PATH} not found')
    ok = False
elif 'JSON.parse(cleaned)' in dist:
    print('  removeCodeBlocks: APPLIED')
else:
    print('  removeCodeBlocks: NOT APPLIED (needs reapply after plugin update)')
    ok = False

# --- Patch 3: max_tokens ---
print('\nPatch 3 (max_tokens):')
if dist is None:
    print(f'  ERROR: {DIST_PATH} not found')
    ok = False
elif 'max_tokens: 8192' in dist:
    print('  max_tokens: 8192 APPLIED')
elif 'max_tokens: 4096' in dist:
    print('  max_tokens: 4096 NOT APPLIED (needs reapply after plugin update)')
    ok = False
else:
    print('  max_tokens: UNKNOWN value')
    ok = False

# --- Result ---
print()
if ok:
    print('All patches applied.')
    sys.exit(0)
else:
    print('Some patches missing. See above.')
    sys.exit(1)
