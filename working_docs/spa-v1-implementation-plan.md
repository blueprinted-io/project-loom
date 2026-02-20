# SPA V1 Implementation Plan (Ordered)

Branch scope: `SPA-Front-end-experiments`
Source spec: `working_docs/spa-v1-ui-spec.md`
Rule: presentation-only pass; no behavior changes.

## Phase 0 — Safety + Working Baseline

1. Confirm branch and commit safety:
   - `git checkout SPA-Front-end-experiments`
   - confirm clean status
2. Confirm comparison servers still available:
   - stable reference on `:8000`
   - SPA work on `:8003`
3. Create implementation checkpoint branch:
   - `git checkout -b spa/v1-ui-pass-queue-detail`

Acceptance:
- Correct branch active
- Local run works before edits

---

## Phase 1 — UI Foundation (Shell + Tokens + Core Primitives)

## Files (expected)
- `lcs_mvp/app/static/style.css` (or SPA-equivalent split CSS files)
- shared layout template/component files used by SPA shell

Tasks:
1. Add design tokens (single light theme):
   - spacing scale
   - typography scale
   - semantic colors (bg/surface/text/border/status)
   - radii/shadows
2. Build left rail shell states:
   - expanded (icon+label)
   - collapsed (icon-only)
   - keyboard-accessible toggle
   - persisted preference (local storage)
3. Build top search-first strip with minimal chrome.
4. Add common card primitives:
   - card container
   - card title/value/meta slots
5. Add status chip primitives with semantic classes.

Acceptance:
- Shell renders across target pages
- Rail expands/collapses correctly
- Tokenized styles in place (no hardcoded random values)

Commit suggestion:
- `feat(ui): add v1 shell, tokens, rail states, and card/chip primitives`

---

## Phase 2 — Review Queue (Primary Screen)

## Files (expected)
- Review queue template/component
- Related list row partial/component
- Queue styling module

Tasks:
1. Convert queue to single merged list (Tasks + Workflows).
2. Ensure row schema displays only:
   - title
   - domain
   - type badge
   - status chip
3. Enforce row action = Open only.
4. Apply reviewer sort priority:
   1) workflow-blocking first
   2) oldest next
   3) everything else
5. Keep task/workflow behavior and backend handlers unchanged.

Acceptance:
- Merged list visual + interaction behavior matches spec
- No quick action buttons beyond Open
- Sorting order verified with test data

Commit suggestion:
- `feat(ui): implement merged review queue with spec-compliant row model`

---

## Phase 3 — Task Detail Presentation Refresh

## Files (expected)
- Task detail template/component
- Task detail styling module

Tasks:
1. Apply new shell and spacing system.
2. Header layout:
   - title
   - domain
   - status chip
3. Make primary actions sticky top-right.
4. Preserve existing review behavior exactly:
   - Approve
   - Return with mandatory free-text comments
5. Improve hierarchy/readability only (no flow changes).

Acceptance:
- Sticky actions functional
- Existing validation/actions unchanged
- Task content fully visible and readable

Commit suggestion:
- `feat(ui): restyle task detail with sticky action rail (no behavior change)`

---

## Phase 4 — Workflow Detail Presentation Refresh

## Files (expected)
- Workflow detail template/component
- Workflow detail styling module

Tasks:
1. Apply new shell/tokens/card hierarchy.
2. Header layout aligned with task detail pattern.
3. Sticky top-right actions.
4. Present included tasks clearly, without implying task non-reusability.
5. Preserve existing workflow behavior/actions.

Acceptance:
- Workflow page visually aligned with queue/task detail
- No review-flow behavior regressions

Commit suggestion:
- `feat(ui): restyle workflow detail and task-list presentation`

---

## Phase 5 — Dashboard Lightweight Stub

## Files (expected)
- Dashboard template/component
- Dashboard card grid module

Tasks:
1. Implement lightweight actionable summary only.
2. Show actionable-scoped counts per role/domain:
   - Workflows: draft/submitted/confirmed/outstanding review
   - Tasks: draft/submitted/confirmed/outstanding review
   - Assessments: draft/submitted/confirmed/outstanding review
   - Last audit entry
3. Ensure count cards link to filtered queue/list targets.

Acceptance:
- Dashboard remains thin and actionable
- No fake/global non-actionable metrics shown

Commit suggestion:
- `feat(ui): add lightweight actionable dashboard stub`

---

## Phase 6 — Cross-Screen Hardening

Tasks:
1. Visual consistency pass:
   - spacing, typography, card rhythm, chip usage
2. State pass:
   - loading/empty/error for queue/dashboard
3. Accessibility pass:
   - keyboard nav
   - visible focus states
   - rail toggle operable via keyboard
4. Responsive pass:
   - desktop 4-column target
   - sane fallback on smaller viewports

Acceptance:
- Meets acceptance checklist in spec doc
- No obvious regressions in core role flows

Commit suggestion:
- `chore(ui): consistency, states, accessibility, and responsive hardening`

---

## Phase 7 — Verification + Merge Prep

Tasks:
1. Run app on `:8003` and sanity-check all 3 role journeys.
2. Capture before/after screenshots for:
   - Review Queue
   - Task Detail
   - Workflow Detail
   - Dashboard stub
3. Validate against `working_docs/spa-v1-ui-spec.md` checklist.
4. Prepare PR summary:
   - explicitly state “presentation-only; behavior preserved”
   - list any known UI debt deferred to v1.1

Final acceptance gate:
- Spec checklist fully reviewed
- No behavior regressions detected
- Ready for stakeholder review

---

## Optional v1.1 (Not in this pass)

- Dark mode implementation (token-driven)
- Dashboard depth expansion
- Additional queue refinements once real usage data arrives
