#!/usr/bin/env python3
"""
Test script to demonstrate the difference between 'light' and 'full' detail levels.
"""
import json
import sys
sys.path.insert(0, '/Users/swisi/Repos/privat/chastease/src')

from chastease.config import Config
from chastease.db import build_engine, build_session_factory
from chastease.models import ChastitySession
from chastease.services.narration import _build_live_snapshot_for_ai

config = Config()
engine = build_engine(config.DATABASE_URL)
session_factory = build_session_factory(engine)
db = session_factory()

SESSION_ID = 'bdceef01-349f-4b1f-ada1-d452e3b9628a'

try:
    session = db.get(ChastitySession, SESSION_ID)
    if not session:
        print(f"❌ Session {SESSION_ID} not found")
        sys.exit(1)

    # Test LIGHT mode
    print("=" * 80)
    print("LIGHT MODE (default - minimal token usage)")
    print("=" * 80)
    light_snapshot = _build_live_snapshot_for_ai(session, mode="light")
    light_json = json.dumps(light_snapshot, ensure_ascii=False, indent=2)
    print(light_json)
    print(f"\n📊 Size: {len(light_json)} chars (~{len(light_json) // 4} tokens)")
    print(f"📝 Fields: {list(light_snapshot.keys())}")
    
    # Test FULL mode
    print("\n" + "=" * 80)
    print("FULL MODE (includes psychogram & setup)")
    print("=" * 80)
    full_snapshot = _build_live_snapshot_for_ai(session, mode="full")
    full_json = json.dumps(full_snapshot, ensure_ascii=False, indent=2)
    print(full_json)
    print(f"\n📊 Size: {len(full_json)} chars (~{len(full_json) // 4} tokens)")
    print(f"📝 Fields: {list(full_snapshot.keys())}")
    
    # Comparison
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print(f"Light mode: {len(light_json)} chars (~{len(light_json) // 4} tokens)")
    print(f"Full mode:  {len(full_json)} chars (~{len(full_json) // 4} tokens)")
    print(f"Difference: {len(full_json) - len(light_json)} chars (~{(len(full_json) - len(light_json)) // 4} tokens)")
    print(f"\n✅ Token savings with light mode: ~{100 * (1 - len(light_json) / len(full_json)):.1f}%")
    
finally:
    db.close()
