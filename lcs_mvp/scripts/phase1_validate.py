#!/usr/bin/env python3
"""Validate that a DB profile adheres to Phase 1 data contract rules.

Rules checked:
1. Domains: Only canonical domains are enabled.
2. Taxonomy: Tasks have no tags (tags_json is empty list).
3. Taxonomy: Workflows may have tags.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
# If this file is at lcs_mvp/scripts/phase1_validate.py
# parents[0] = scripts
# parents[1] = lcs_mvp
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import _db_path_for_key, PHASE1_OPERATIONAL_DOMAINS

def validate_profile(profile: str) -> bool:
    db_path = _db_path_for_key(profile)
    print(f"Validating profile '{profile}' at {db_path}...")
    
    if not Path(db_path).exists():
        print(f"❌ DB file not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    failures = 0

    # 1. Domain Validation
    print("--- Domain Validation ---")
    rows = conn.execute("SELECT name, disabled_at FROM domains").fetchall()
    active_domains = {r["name"] for r in rows if r["disabled_at"] is None}
    canonical_set = set(PHASE1_OPERATIONAL_DOMAINS)
    
    # Check if all active are canonical
    invalid_active = active_domains - canonical_set
    if invalid_active:
        print(f"❌ Non-canonical domains are ACTIVE: {invalid_active}")
        failures += 1
    else:
        print("✅ All active domains are canonical.")

    # Check if all canonical are present (active or disabled)
    all_present_domains = {r["name"] for r in rows}
    missing_canonical = canonical_set - all_present_domains
    if missing_canonical:
        print(f"❌ Missing canonical domains in registry: {missing_canonical}")
        failures += 1
    else:
        print("✅ Registry contains all canonical domains.")


    # 2. Task Tag Validation (Should be empty)
    print("\n--- Task Tag Validation ---")
    rows = conn.execute("SELECT record_id, version, tags_json FROM tasks").fetchall()
    task_failures = 0
    for r in rows:
        tags = json.loads(r["tags_json"] or "[]")
        if tags:
            print(f"❌ Task {r['record_id']} v{r['version']} has tags: {tags}")
            task_failures += 1
    
    if task_failures == 0:
        print("✅ All tasks are tagless.")
    else:
        print(f"❌ Found {task_failures} tasks with forbidden tags.")
        failures += 1

    conn.close()
    
    if failures == 0:
        print("\n✅ VALIDATION PASSED: Profile adheres to Phase 1 contract.")
        return True
    else:
        print(f"\n❌ VALIDATION FAILED: {failures} rule violations found.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Phase 1 data contract.")
    parser.add_argument("--profile", default="blueprinted_org", help="DB profile key to validate")
    args = parser.parse_args()
    
    success = validate_profile(args.profile)
    sys.exit(0 if success else 1)
