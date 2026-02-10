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
        ), "confirmed"),
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
        ), "confirmed"),
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

    # More reusable household SOP tasks (to reduce cognitive load in demos while still showing workflow reuse)
    tasks += [
        # Personal care
        (task(
            "Wash face",
            "Face is cleaned and dried.",
            "Wash face",[
                step("Wash hands before touching face.", "Hands are clean.", actions=["Wash hands"]),
                step("Wet face and apply cleanser (if used).", "Face is evenly wet and cleanser applied.", actions=["Wet", "Apply"], notes="Use a mild cleanser suitable for the person; avoid eye irritation."),
                step("Rinse and pat dry with a clean towel.", "Face is rinsed and dry.", actions=["Rinse", "Pat dry"]),
            ],
            deps=["Water", "Towel", "Cleanser (optional)"],
            facts=["Using a clean towel reduces recontamination."],
            concepts=["Gentle technique reduces irritation."],
            domain="personal_care",
            tags=["hygiene"],
        ), "confirmed"),
        (task(
            "Shower (standard)",
            "A shower is completed and the area is left safe.",
            "Take shower",[
                step("Set water temperature to a safe, comfortable level.", "Water temperature is set.", actions=["Adjust temperature"], notes="Avoid excessively hot water to reduce irritation and burn risk."),
                step("Wash body and rinse thoroughly.", "Body is washed and rinsed.", actions=["Use soap/body wash", "Rinse"]),
                step("Turn off water and dry off; hang towel to dry.", "Water off; towel hung.", actions=["Turn off", "Dry", "Hang towel"]),
            ],
            deps=["Shower", "Soap", "Towel"],
            facts=["Wet floors increase slip risk."],
            concepts=["Resetting the space reduces next-time friction."],
            domain="personal_care",
            tags=["hygiene"],
        ), "submitted"),
        (task(
            "Get dressed (prepare outfit)",
            "Outfit is selected and ready to wear.",
            "Prepare outfit",[
                step("Select clothing suitable for the day’s activities.", "Clothing selected.", actions=["Check schedule/weather"], notes="If uncertain, choose a neutral option that supports the primary objective."),
                step("Check for obvious issues (stains, missing buttons).", "Issues identified or none found.", actions=["Inspect"]),
                step("Place outfit in a designated ready area.", "Outfit staged.", actions=["Stage"]),
            ],
            deps=["Clothing"],
            facts=["Staging reduces morning decision load."],
            concepts=["Reduce friction by deciding once."],
            domain="household",
            tags=["routine"],
        ), "confirmed"),

        # Kitchen + drinks
        (task(
            "Prepare tea (loose leaf)",
            "Loose-leaf tea is brewed and served.",
            "Brew loose-leaf tea",[
                step("Place loose tea in infuser/teapot.", "Tea is measured into infuser.", actions=["Measure leaves"], notes="Use a strainer to avoid leaves in cup."),
                step("Add boiled water and steep for the recommended time.", "Tea steeped to target time.", actions=["Pour", "Set timer"], notes="Steeping time varies by tea type."),
                step("Remove infuser/strain and serve.", "Tea served without loose leaves.", actions=["Remove infuser", "Serve"]),
            ],
            deps=["Loose leaf tea", "Infuser/teapot", "Boiled water"],
            facts=["Tea-to-water ratio affects strength."],
            concepts=["Repeatability comes from consistent measurement + timing."],
            domain="kitchen",
            tags=["beverages"],
        ), "confirmed"),
        (task(
            "Prepare coffee (French press)",
            "French press coffee is brewed and served safely.",
            "Brew coffee (French press)",[
                step("Warm the press (optional) and add ground coffee.", "Ground coffee added.", actions=["Pre-warm", "Measure grounds"], notes="Use a coarse grind to reduce sediment."),
                step("Add hot water and start timer.", "Coffee is steeping.", actions=["Pour", "Stir gently", "Set timer"]),
                step("Press plunger slowly and serve.", "Coffee served.", actions=["Press", "Pour"], notes="Do not force the plunger; check for blockage."),
            ],
            deps=["French press", "Ground coffee", "Hot water"],
            facts=["Steep time affects extraction and bitterness."],
            concepts=["Control time + ratio for consistent results."],
            domain="kitchen",
            tags=["beverages"],
        ), "confirmed"),
        (task(
            "Load dishwasher",
            "Dishwasher is loaded safely and ready to run.",
            "Load dishwasher",[
                step("Scrape food into bin/compost.", "Loose food removed.", actions=["Scrape"], notes="Do not pre-rinse heavily unless required; follow dishwasher guidance."),
                step("Place items in racks with spray access.", "Items placed without blocking spray arms.", actions=["Load plates", "Load cups"], notes="Point dirty surfaces toward spray jets."),
                step("Add detergent and select an appropriate cycle.", "Detergent added; cycle selected.", actions=["Add detergent", "Select cycle"]),
            ],
            deps=["Dishwasher", "Detergent"],
            facts=["Overloading reduces cleaning effectiveness."],
            concepts=["Orientation + spacing improves wash coverage."],
            domain="kitchen",
            tags=["cleanup"],
        ), "confirmed"),
        (task(
            "Run dishwasher",
            "Dishwasher cycle runs to completion.",
            "Run dishwasher",[
                step("Confirm dishwasher is loaded and door seals.", "Door closes and latches.", actions=["Close", "Latch"]),
                step("Start cycle.", "Cycle is running.", actions=["Press start"], notes="If delayed start is used, confirm time aligns with needs."),
                step("Verify completion.", "Cycle complete.", actions=["Check status"], notes="Address standing water if present."),
            ],
            deps=["Loaded dishwasher"],
            facts=["Some cycles take 1–3 hours depending on settings."],
            concepts=["Confirm completion before unloading."],
            domain="kitchen",
            tags=["cleanup"],
        ), "confirmed"),
        (task(
            "Unload dishwasher",
            "Clean dishes are put away and dishwasher is ready for reuse.",
            "Unload dishwasher",[
                step("Open dishwasher and allow steam to vent.", "Steam vented.", actions=["Open door", "Wait"], notes="Use caution with hot steam."),
                step("Unload bottom rack first.", "Bottom rack unloaded.", actions=["Unload plates", "Unload utensils"]),
                step("Put items away and reset racks.", "Items stored; racks reset.", actions=["Put away", "Reset"]),
            ],
            deps=["Completed dishwasher cycle"],
            facts=["Unloading top rack first can drip water onto dry items."],
            concepts=["Standard order prevents rework."],
            domain="kitchen",
            tags=["cleanup"],
        ), "confirmed"),
        (task(
            "Hand-wash dishes",
            "Dishes are washed, rinsed, and left to dry.",
            "Hand-wash dishes",[
                step("Prepare sink/basin with hot soapy water.", "Soapy water prepared.", actions=["Fill", "Add soap"], notes="Water should be hot but safe for hands."),
                step("Wash items, starting with least greasy.", "Items washed and free of residue.", actions=["Scrub", "Work in batches"], notes="Change water if it becomes dirty."),
                step("Rinse and place on rack to air-dry.", "No soap residue; items drying.", actions=["Rinse", "Rack"]),
            ],
            deps=["Dish soap", "Sponge/brush", "Water", "Drying rack"],
            facts=["Order reduces cross-contamination from greasy items."],
            concepts=["Batching prevents sink overload."],
            domain="kitchen",
            tags=["cleanup"],
        ), "confirmed"),

        # Cleaning
        (task(
            "Wipe kitchen counter surface",
            "Kitchen counter is wiped and visibly clean.",
            "Wipe surface",[
                step("Clear items from the surface.", "Surface is clear.", actions=["Move items"], notes="Group items to reduce rework."),
                step("Wipe with appropriate cleaner.", "Surface wiped evenly.", actions=["Spray cleaner", "Wipe"], notes="Check cleaner compatibility with the surface material."),
                step("Return items and dispose of used wipes/cloths.", "Items returned; waste disposed.", actions=["Return", "Dispose"]),
            ],
            deps=["Cloth/paper towel", "Cleaner"],
            facts=["Some cleaners require dwell time to disinfect; follow label if needed."],
            concepts=["Clear → clean → reset keeps work repeatable."],
            domain="cleaning",
            tags=["cleaning"],
        ), "confirmed"),
        (task(
            "Dust surfaces (room)",
            "Visible dust is removed from common surfaces.",
            "Dust room",[
                step("Start at higher surfaces and work down.", "High surfaces dusted.", actions=["Top shelves", "Frames"], notes="Top-down prevents re-dusting."),
                step("Dust horizontal surfaces.", "Main surfaces dusted.", actions=["Tables", "Sills"]),
                step("Dispose or launder cloths appropriately.", "Cloths handled; area reset.", actions=["Shake/Dispose", "Launder"]),
            ],
            deps=["Duster/cloth"],
            facts=["Dust settles downward over time."],
            concepts=["Top-down order reduces rework."],
            domain="cleaning",
            tags=["cleaning"],
        ), "confirmed"),
        (task(
            "Mop hard floor",
            "Hard floor is mopped and left to dry safely.",
            "Mop floor",[
                step("Sweep/vacuum first.", "Loose debris removed.", actions=["Sweep", "Vacuum"], notes="Mopping over debris can scratch surfaces."),
                step("Prepare mop solution and wring mop.", "Solution prepared; mop damp.", actions=["Prepare", "Wring"], notes="Use manufacturer guidance for floor type."),
                step("Mop in sections and allow to dry.", "Floor mopped; drying in progress.", actions=["Mop", "Air-dry"], notes="Post a wet-floor warning if people may walk through."),
            ],
            deps=["Mop", "Bucket", "Cleaner"],
            facts=["Excess water can damage some flooring materials."],
            concepts=["Prep → clean → dry reduces slip risk."],
            domain="cleaning",
            tags=["cleaning"],
        ), "draft"),
        (task(
            "Take out trash",
            "Trash is removed and bins are reset.",
            "Take out trash",[
                step("Tie bag securely.", "Bag is sealed.", actions=["Tie"]),
                step("Move bag to external bin.", "Bag placed in external bin.", actions=["Carry", "Place"], notes="Avoid tearing; double-bag if needed."),
                step("Replace liner and sanitize bin rim if needed.", "New liner installed; rim cleaned.", actions=["Replace liner", "Wipe rim"]),
            ],
            deps=["Trash bags"],
            facts=["Sealed bags reduce odor and leakage."],
            concepts=["Resetting prevents next-time friction."],
            domain="household",
            tags=["routine"],
        ), "confirmed"),

        # Laundry
        (task(
            "Sort laundry",
            "Laundry is sorted into appropriate loads.",
            "Sort laundry",[
                step("Check care labels and separate by requirements.", "Loads separated by care needs.", actions=["Check labels"], notes="If unsure, wash on cold and air-dry as a safe default."),
                step("Separate heavy items from delicates.", "Delicates separated.", actions=["Separate"]),
                step("Empty pockets and close zippers.", "Pockets empty; zippers closed.", actions=["Empty pockets", "Zip"]),
            ],
            deps=["Laundry basket"],
            facts=["Mixed loads can cause color transfer or fabric damage."],
            concepts=["Sorting reduces risk and rework."],
            domain="laundry",
            tags=["laundry"],
        ), "confirmed"),
        (task(
            "Run laundry wash cycle",
            "Laundry wash cycle runs to completion.",
            "Wash laundry",[
                step("Load washer without overfilling.", "Washer loaded.", actions=["Load"], notes="Overfilling reduces cleaning effectiveness."),
                step("Add detergent and select appropriate cycle.", "Detergent added; cycle selected.", actions=["Add detergent", "Select cycle"]),
                step("Start cycle and verify it begins.", "Cycle running.", actions=["Start", "Confirm"]),
            ],
            deps=["Washing machine", "Detergent"],
            facts=["Different cycles balance agitation, temperature, and time."],
            concepts=["Appropriate settings preserve fabric and improve outcomes."],
            domain="laundry",
            tags=["laundry"],
        ), "confirmed"),
        (task(
            "Dry laundry",
            "Laundry is dried appropriately and safely.",
            "Dry laundry",[
                step("Check care labels for drying restrictions.", "Drying method selected.", actions=["Check labels"], notes="Air-dry delicates when in doubt."),
                step("Dry using dryer or air-dry setup.", "Drying started.", actions=["Start dryer"], notes="Clean lint filter before drying."),
                step("Verify laundry is dry and remove promptly.", "Laundry removed and ready.", actions=["Check", "Remove"]),
            ],
            deps=["Dryer or drying rack"],
            facts=["Lint buildup can be a fire risk; clean filters regularly."],
            concepts=["Prompt removal reduces wrinkles."],
            domain="laundry",
            tags=["laundry"],
        ), "confirmed"),
        (task(
            "Fold laundry",
            "Laundry is folded and ready to put away.",
            "Fold laundry",[
                step("Sort items by type.", "Items grouped.", actions=["Group"]),
                step("Fold items consistently.", "Items folded.", actions=["Fold"], notes="A consistent fold reduces drawer clutter."),
                step("Stack or basket items by destination.", "Stacks prepared for put-away.", actions=["Stack", "Basket"]),
            ],
            deps=["Clean laundry"],
            facts=["Folding reduces wrinkling and improves storage efficiency."],
            concepts=["Standardization reduces decision fatigue."],
            domain="laundry",
            tags=["laundry"],
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
        # Morning routines (alts)
        (
            "Morning routine (tea)",
            "Complete basic morning hygiene and prepare tea.",
            [inserted["Wash hands"], inserted["Wash face"], inserted["Brush teeth"], inserted["Prepare tea (tea bag)"]],
            "confirmed",
        ),
        (
            "Morning routine (coffee)",
            "Complete basic morning hygiene and prepare coffee.",
            [inserted["Wash hands"], inserted["Wash face"], inserted["Brush teeth"], inserted["Prepare instant coffee"]],
            "submitted",
        ),
        (
            "Morning routine (coffee - French press)",
            "Complete basic morning hygiene and prepare French press coffee.",
            [inserted["Wash hands"], inserted["Brush teeth"], inserted["Prepare coffee (French press)"]],
            "confirmed",
        ),

        # Bedroom quick reset
        (
            "Guest-ready bedroom (10 minutes)",
            "Make the bedroom look tidy and presentable quickly.",
            [inserted["Tidy a room (5-minute reset)"], inserted["Make the bed"]],
            "draft",
        ),

        # Kitchen reset variants
        (
            "Kitchen reset (dishwasher)",
            "Reset the kitchen after a meal using the dishwasher.",
            [inserted["Wipe kitchen counter surface"], inserted["Load dishwasher"], inserted["Run dishwasher"]],
            "confirmed",
        ),
        (
            "Kitchen reset (hand-wash)",
            "Reset the kitchen after a meal without using a dishwasher.",
            [inserted["Wipe kitchen counter surface"], inserted["Hand-wash dishes"]],
            "confirmed",
        ),
        (
            "Dishwasher completion",
            "Unload dishwasher and reset the counter.",
            [inserted["Unload dishwasher"], inserted["Wipe kitchen counter surface"]],
            "confirmed",
        ),

        # Cleaning
        (
            "Quick floor refresh",
            "Vacuum a room safely and reset equipment.",
            [inserted["Vacuum a room"]],
            "confirmed",
        ),
        (
            "Dust + vacuum",
            "Remove dust then vacuum the floor.",
            [inserted["Dust surfaces (room)"], inserted["Vacuum a room"]],
            "confirmed",
        ),

        # Laundry loop
        (
            "Laundry cycle (standard)",
            "Sort, wash, dry, and fold laundry.",
            [inserted["Sort laundry"], inserted["Run laundry wash cycle"], inserted["Dry laundry"], inserted["Fold laundry"]],
            "confirmed",
        ),

        # Beverage alt workflow
        (
            "Hot drink options (tea + coffee + chocolate)",
            "Prepare a hot drink using tea, coffee, or hot chocolate.",
            [inserted["Prepare tea (loose leaf)"], inserted["Prepare instant coffee"], inserted["Prepare hot chocolate (powder)"]],
            "confirmed",
        ),

        # End-of-day reset
        (
            "End-of-day shutdown",
            "Do a short reset to make tomorrow easier.",
            [inserted["Take out trash"], inserted["Wipe kitchen counter surface"], inserted["Tidy a room (5-minute reset)"]],
            "submitted",
        ),

        # Personal care extended
        (
            "Full hygiene (including floss)",
            "Complete a thorough hygiene sequence.",
            [inserted["Wash hands"], inserted["Brush teeth"], inserted["Floss teeth"], inserted["Wash face"]],
            "submitted",
        ),

        # Prep workflow to show staging
        (
            "Prepare for tomorrow",
            "Stage clothing and essentials to reduce next-morning friction.",
            [inserted["Get dressed (prepare outfit)"]],
            "confirmed",
        ),

        # A couple more compositions to approach ~20 workflows
        (
            "Minimal morning essentials",
            "Complete minimal hygiene steps.",
            [inserted["Wash hands"], inserted["Brush teeth"]],
            "confirmed",
        ),
        (
            "Beverage setup",
            "Prepare mug and hot water for beverages.",
            [inserted["Clean a mug/cup"], inserted["Boil water (kettle)"]],
            "confirmed",
        ),
        (
            "Weekly light clean",
            "Dust, vacuum, and wipe key kitchen surfaces.",
            [inserted["Dust surfaces (room)"], inserted["Vacuum a room"], inserted["Wipe kitchen counter surface"]],
            "confirmed",
        ),
        (
            "Shower + reset",
            "Take a shower and ensure towel is drying.",
            [inserted["Shower (standard)"]],
            "submitted",
        ),
        (
            "Mop floors (draft)",
            "Mop hard floors and allow to dry.",
            [inserted["Mop hard floor"]],
            "draft",
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
