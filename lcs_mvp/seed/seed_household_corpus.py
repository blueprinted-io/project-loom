"""Seed a household SOP corpus into a custom SQLite DB profile.

Purpose:
- Provide a low-cognitive-load demo dataset (non-technical) so audiences focus on the governance loop.
- Still demonstrate reuse: workflows are composed from atomic reusable tasks.

Creates a custom DB file: lcs_<key>.db (default: lcs_household.db)

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/seed_household_corpus.py --force

Then in the app: Admin → Switch database → household

Notes:
- Demo content is structurally correct but not authoritative guidance.
- Statuses are seeded intentionally to support review-queue demos.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

# Allow running as: python seed/seed_household_corpus.py
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


ACTOR = "seed"
SEED_NOTE = "seed_household_corpus_v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def step(text: str, completion: str, actions: list[str] | None = None, notes: str = "") -> dict[str, object]:
    return {
        "text": text,
        "actions": actions if actions is not None else [],
        "notes": (notes or "").strip(),
        "completion": completion,
    }


def task(
    title: str,
    outcome: str,
    procedure_name: str,
    steps: list[dict[str, object]],
    deps: list[str],
    facts: list[str],
    concepts: list[str],
    domain: str,
    tags: list[str] | None = None,
    irreversible: int = 0,
) -> dict:
    return {
        "title": title,
        "outcome": outcome,
        "procedure_name": procedure_name,
        "steps": steps,
        "deps": deps,
        "facts": facts,
        "concepts": concepts,
        "domain": domain,
        "tags": tags or [],
        "irreversible": irreversible,
    }


@dataclass
class Ref:
    rid: str
    ver: int
    title: str


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="household")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    from app.main import _db_path_for_key, init_db_path, _seed_demo_users, _seed_demo_domains, _seed_demo_entitlements

    key = (args.key or "household").strip().lower()
    db_path = _db_path_for_key(key)

    if os.path.exists(db_path) and not args.force:
        raise SystemExit(f"DB already exists: {db_path} (use --force to overwrite)")
    if os.path.exists(db_path) and args.force:
        os.remove(db_path)

    init_db_path(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Seed auth + domain registry/entitlements
    _seed_demo_users(conn)
    _seed_demo_domains(conn)
    _seed_demo_entitlements(conn)

    # Add household domains
    now = utc_now_iso()
    for d in ["household", "kitchen", "personal_care", "cleaning"]:
        conn.execute(
            "INSERT OR IGNORE INTO domains(name, created_at, created_by) VALUES (?,?,?)",
            (d, now, ACTOR),
        )

    def insert_task(t: dict, status: str) -> Ref:
        rid = str(uuid.uuid4())
        ver = 1
        conn.execute(
            """
            INSERT INTO tasks(
              record_id, version, status,
              title, outcome, facts_json, concepts_json,
              procedure_name, steps_json, dependencies_json,
              irreversible_flag, task_assets_json,
              domain, tags_json, meta_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                ver,
                status,
                t["title"],
                t["outcome"],
                j(t["facts"]),
                j(t["concepts"]),
                t["procedure_name"],
                j(t["steps"]),
                j(t["deps"]),
                int(t.get("irreversible", 0)),
                "[]",
                t["domain"],
                j(t.get("tags") or []),
                j({"seed": SEED_NOTE}),
                now,
                now,
                ACTOR,
                ACTOR,
                (now if status in ("confirmed", "deprecated") else None),
                (ACTOR if status in ("confirmed", "deprecated") else None),
                ("Seeded" if status != "draft" else None),
                0,
                "",
            ),
        )
        return Ref(rid, ver, t["title"])

    # --- Build reusable tasks ---
    tasks: list[tuple[dict, str]] = []

    # Personal care primitives
    tasks += [
        (task(
            "Wash hands",
            "Hands are cleaned and dried appropriately.",
            "Wash hands",[
                step("Wet hands with clean running water.", "Hands are visibly wet.", actions=["Turn on tap", "Adjust to comfortable temperature"]),
                step("Apply soap and lather all hand surfaces for at least 20 seconds.", "All surfaces were lathered for ~20 seconds.", actions=["Rub palms, backs of hands, between fingers, under nails"], notes="If soap is unavailable, use hand sanitizer (60%+ alcohol) until dry."),
                step("Rinse thoroughly and dry with a clean towel.", "Hands are rinsed and dry.", actions=["Rinse", "Dry"]),
            ],
            deps=["Clean water", "Soap", "Towel"],
            facts=["Effective handwashing reduces spread of germs.", "Drying hands helps reduce recontamination."],
            concepts=["Friction + time improves cleaning effectiveness."],
            domain="personal_care",
            tags=["hygiene"],
        ), "confirmed"),
        (task(
            "Brush teeth",
            "Teeth are brushed thoroughly and mouth feels clean.",
            "Brush teeth",[
                step("Apply toothpaste to toothbrush.", "Toothbrush has toothpaste applied.", actions=["Use a pea-sized amount"], notes="If toothpaste is unavailable, brush with water to remove debris."),
                step("Brush all tooth surfaces for ~2 minutes.", "All surfaces were brushed.", actions=["Outer, inner, chewing surfaces", "Gentle circular motion"], notes="If you have dental guidance from a professional, follow it."),
                step("Spit and rinse toothbrush; store to air-dry.", "Toothbrush is rinsed and stored upright.", actions=["Rinse brush", "Place in holder"]),
            ],
            deps=["Toothbrush", "Toothpaste", "Sink"],
            facts=["Brushing removes plaque from tooth surfaces."],
            concepts=["Consistency matters more than intensity."],
            domain="personal_care",
            tags=["hygiene"],
        ), "confirmed"),
        (task(
            "Floss teeth",
            "Between-tooth areas are cleaned.",
            "Floss teeth",[
                step("Cut an appropriate length of floss and wrap around fingers.", "Floss is prepared and controlled.", actions=["Use ~45cm / 18in"], notes="Alternatives: floss picks or interdental brushes if appropriate."),
                step("Clean between each pair of teeth using a gentle C-shape motion.", "All target gaps were flossed.", actions=["Slide gently", "Avoid snapping"], notes="If gums bleed persistently, consult a dental professional."),
                step("Dispose of floss and rinse mouth if desired.", "Floss disposed; mouth feels clean.", actions=["Dispose", "Rinse"]),
            ],
            deps=["Floss"],
            facts=["Flossing targets areas a toothbrush may miss."],
            concepts=["Gentle technique prevents gum injury."],
            domain="personal_care",
            tags=["hygiene"],
        ), "submitted"),
    ]

    # Kitchen primitives
    tasks += [
        (task(
            "Boil water (kettle)",
            "Water is boiled safely and ready for use.",
            "Boil water",[
                step("Fill kettle with required amount of water.", "Kettle is filled to the needed level.", actions=["Check min/max markers"], notes="Use fresh cold water for better taste."),
                step("Switch on kettle and wait until it boils.", "Kettle indicates boil complete.", actions=["Turn on", "Wait"]),
                step("Pour boiled water carefully into the vessel.", "Hot water is in the vessel without spills.", actions=["Pour slowly"], notes="Use caution around steam and hot surfaces."),
            ],
            deps=["Kettle", "Water", "Power outlet"],
            facts=["Boiling water is ~100°C at sea level."],
            concepts=["Use the minimum effective volume to reduce waiting time."],
            domain="kitchen",
            tags=["beverages"],
            irreversible=0,
        ), "confirmed"),
        (task(
            "Clean a mug/cup", "A mug is clean and ready to use.", "Clean mug",[
                step("Rinse mug to remove residue.", "Visible residue is removed.", actions=["Rinse with warm water"]),
                step("Wash with dish soap and a sponge/brush.", "Mug is washed and free of grease.", actions=["Soap", "Scrub"], notes="If using a shared sponge, replace regularly to avoid odor buildup."),
                step("Rinse and air-dry or towel-dry.", "No soap remains; mug is dry enough to use.", actions=["Rinse", "Dry"]),
            ],
            deps=["Dish soap", "Sponge/brush", "Water"],
            facts=["Soap helps remove oils and residues."],
            concepts=["Clean tools reduce cross-contamination."],
            domain="kitchen",
            tags=["cleanup"],
        ), "draft"),
    ]

    # Drinks (reuse boil water + clean mug)
    tasks += [
        (task(
            "Prepare tea (tea bag)",
            "Tea is brewed to desired strength.",
            "Brew tea",[
                step("Place a tea bag in a mug.", "Tea bag is in mug.", actions=["Select tea"], notes="Use a clean mug; pre-warm if desired."),
                step("Add boiled water and steep for the recommended time.", "Tea is steeped for the target duration.", actions=["Pour water", "Set timer"], notes="Steeping too long can increase bitterness depending on tea type."),
                step("Remove tea bag and add milk/sugar if desired.", "Tea bag removed; tea adjusted to preference.", actions=["Remove bag", "Stir"]),
            ],
            deps=["Tea bags", "Mug", "Boiled water"],
            facts=["Steeping time affects extraction and strength."],
            concepts=["Control variables: water temperature, time, and ratio."],
            domain="kitchen",
            tags=["beverages"],
        ), "confirmed"),
        (task(
            "Prepare instant coffee",
            "Coffee is prepared to desired strength.",
            "Make instant coffee",[
                step("Add instant coffee to a mug.", "Coffee granules are in mug.", actions=["Measure 1–2 tsp"], notes="Adjust to taste."),
                step("Add boiled water and stir.", "Coffee is dissolved and mixed.", actions=["Pour", "Stir"]),
                step("Add milk/sugar if desired.", "Drink is adjusted to preference.", actions=["Add", "Stir"], notes="Consider temperature: add cold milk after stirring to avoid clumps."),
            ],
            deps=["Instant coffee", "Mug", "Boiled water"],
            facts=["Stirring helps dissolve granules evenly."],
            concepts=["Strength depends on coffee-to-water ratio."],
            domain="kitchen",
            tags=["beverages"],
        ), "submitted"),
        (task(
            "Prepare hot chocolate (powder)",
            "Hot chocolate is prepared and served safely.",
            "Make hot chocolate",[
                step("Add hot chocolate powder to a mug.", "Powder is in mug.", actions=["Measure per packet/tin"], notes="Some powders mix better with a small amount of warm water first."),
                step("Add hot water or hot milk and whisk/stir.", "Powder is fully mixed; no dry clumps.", actions=["Add liquid", "Stir/whisk"], notes="If using milk, heat it safely and avoid boiling over."),
                step("Taste and adjust sweetness/strength.", "Drink matches target taste.", actions=["Taste", "Adjust"]),
            ],
            deps=["Hot chocolate powder", "Mug", "Hot water or hot milk"],
            facts=["Clumping is reduced by gradual mixing."],
            concepts=["Texture is controlled by mixing technique."],
            domain="kitchen",
            tags=["beverages"],
        ), "confirmed"),
    ]

    # Household/cleaning primitives
    tasks += [
        (task(
            "Make the bed",
            "Bed is made neatly and is ready for use.",
            "Make bed",[
                step("Remove items from the bed surface.", "Bed surface is clear.", actions=["Move items to chair/basket"], notes="If you’re short on time, prioritize clearing + straightening."),
                step("Straighten fitted sheet and top sheet.", "Sheets are aligned and smooth.", actions=["Pull corners", "Smooth wrinkles"]),
                step("Arrange duvet/blanket and pillows.", "Top layer is aligned; pillows placed.", actions=["Shake out", "Align edges"]),
            ],
            deps=["Bedding"],
            facts=["A made bed reduces clutter and makes the room feel tidier."],
            concepts=["Small visible wins improve perceived order."],
            domain="household",
            tags=["routine"],
        ), "confirmed"),
        (task(
            "Tidy a room (5-minute reset)",
            "Room is visibly tidier with items returned to their place.",
            "5-minute tidy",[
                step("Set a 5-minute timer.", "Timer is running.", actions=["Use phone timer"], notes="Timeboxing prevents perfectionism."),
                step("Collect obvious items and put them in a single basket/stack.", "Loose items are collected.", actions=["Grab basket"], notes="Do a second pass only if time remains."),
                step("Return items to their home locations.", "Major items are put away.", actions=["Put away"], notes="If an item has no home, create a temporary ‘inbox’ location."),
            ],
            deps=["Timer", "Basket (optional)"],
            facts=["Short resets reduce the effort required for deep cleaning later."],
            concepts=["Triage: obvious wins first."],
            domain="household",
            tags=["routine"],
        ), "returned"),
        (task(
            "Vacuum a room",
            "Floor is vacuumed and visibly free of loose debris.",
            "Vacuum room",[
                step("Clear small items from the floor.", "Floor is clear of objects that block vacuuming.", actions=["Pick up toys/cables"], notes="Move fragile items to a safe surface."),
                step("Vacuum edges first, then the main floor area.", "Edges and main area are vacuumed.", actions=["Use edge tool if available"], notes="If the vacuum clogs, switch off before clearing."),
                step("Empty/clean vacuum collection as needed.", "Vacuum is ready for next use.", actions=["Empty bin", "Check filter"]),
            ],
            deps=["Vacuum cleaner"],
            facts=["Edges accumulate dust; doing edges first reduces rework."],
            concepts=["Consistency prevents buildup."],
            domain="cleaning",
            tags=["cleaning"],
        ), "confirmed"),
    ]

    # Insert tasks
    inserted: dict[str, Ref] = {}
    for t, status in tasks:
        r = insert_task(t, status)
        inserted[t["title"]] = r

    # --- Workflows ---
    def insert_workflow(title: str, objective: str, refs: list[Ref], status: str) -> tuple[str, int]:
        rid = str(uuid.uuid4())
        ver = 1
        domains = sorted({(conn.execute('SELECT domain FROM tasks WHERE record_id=? AND version=?',(r.rid,r.ver)).fetchone()[0] or '').strip() for r in refs if r})
        conn.execute(
            """
            INSERT INTO workflows(record_id, version, status, title, objective, domains_json, tags_json, meta_json,
                                 created_at, updated_at, created_by, updated_by, reviewed_at, reviewed_by, change_note,
                                 needs_review_flag, needs_review_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                ver,
                status,
                title,
                objective,
                j([d for d in domains if d]),
                j(["household_sop"]),
                j({"seed": SEED_NOTE}),
                now,
                now,
                ACTOR,
                ACTOR,
                (now if status == "confirmed" else None),
                (ACTOR if status == "confirmed" else None),
                "Seeded",
                0,
                "",
            ),
        )
        # refs
        for i, r in enumerate(refs, start=1):
            conn.execute(
                "INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version) VALUES (?,?,?,?,?)",
                (rid, ver, i, r.rid, r.ver),
            )
        return rid, ver

    wf_defs = [
        (
            "Morning routine (tea)",
            "Complete a simple morning hygiene + tea routine.",
            [inserted["Wash hands"], inserted["Brush teeth"], inserted["Prepare tea (tea bag)"]],
            "confirmed",
        ),
        (
            "Morning routine (coffee)",
            "Complete a simple morning hygiene + coffee routine.",
            [inserted["Wash hands"], inserted["Brush teeth"], inserted["Prepare instant coffee"]],
            "submitted",
        ),
        (
            "Guest-ready bedroom (10 minutes)",
            "Make the bedroom look tidy and presentable quickly.",
            [inserted["Tidy a room (5-minute reset)"], inserted["Make the bed"]],
            "draft",
        ),
        (
            "Quick floor refresh", "Vacuum a room safely and reset equipment.", [inserted["Vacuum a room"]], "confirmed"
        ),
        (
            "Hot drink options (tea + chocolate)",
            "Prepare a hot drink using either tea or hot chocolate.",
            [inserted["Prepare tea (tea bag)"], inserted["Prepare hot chocolate (powder)"]],
            "confirmed",
        ),
    ]

    for title, obj, refs, status in wf_defs:
        # Ensure confirmed workflows only reference confirmed tasks.
        if status == "confirmed":
            for r in refs:
                st = conn.execute("SELECT status FROM tasks WHERE record_id=? AND version=?", (r.rid, r.ver)).fetchone()[0]
                if st != "confirmed":
                    raise SystemExit(f"Seed error: confirmed workflow '{title}' references non-confirmed task '{r.title}' ({st})")
        insert_workflow(title, obj, refs, status)

    conn.commit()

    # Summary
    tc = conn.execute("SELECT status, COUNT(*) c FROM tasks GROUP BY status").fetchall()
    wc = conn.execute("SELECT status, COUNT(*) c FROM workflows GROUP BY status").fetchall()
    print(f"Seeded household corpus into {db_path}")
    print("Tasks:", [(r[0], r[1]) for r in tc])
    print("Workflows:", [(r[0], r[1]) for r in wc])


if __name__ == "__main__":
    main()
