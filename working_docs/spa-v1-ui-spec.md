# SPA V1 UI Spec

Status: Draft v1 (agreed baseline)
Branch scope: `SPA-Front-end-experiments` only
Behavior rule: Preserve existing system behavior from `main`; this pass changes presentation only.

## 1) Layout Contract (Global)

- Visual target: operational, dense, card-driven UI.
- Full-height left rail with two states:
  - Expanded: icon + label
  - Collapsed: icon-only
- Minimal top chrome; search-first top area.
- Desktop density target: 4-column card grid.
- Theme: single light theme for v1 (dark mode deferred).
- Status display: colored chips.
- Detail views: primary actions sticky at top-right while scrolling.

## 2) Screen Specs

### A) Dashboard (Lightweight Actionable Summary Stub)

Purpose: quick role/domain-scoped triage, not deep interaction.

Cards (actionable only for current user role/domain):
- Workflows: `# draft`, `# submitted`, `# confirmed`, `# outstanding for review`
- Tasks: `# draft`, `# submitted`, `# confirmed`, `# outstanding for review`
- Assessments: `# draft`, `# submitted`, `# confirmed`, `# outstanding for review`
- Last audit: latest audit list entry

Behavior:
- Card click navigates to relevant filtered list/queue.

### B) Review Queue (Primary Work Surface)

Purpose: unified intake for review actions.

- Single merged list for Tasks + Workflows.
- Row fields:
  - Title
  - Domain
  - Type badge (Task/Workflow)
  - Status chip
- Row quick action: Open only.

Sorting priority (Reviewer):
1. Items blocking workflow progression (derived from workflow-side flag/linkage)
2. Oldest remaining items
3. Everything else

Role-specific focus:
- Author: prioritize returned items (merged list with type badges)
- Reviewer: review queue priority above
- Admin: broad governance/review view

Constraint:
- Do not imply one-to-one task/workflow ownership in presentation. Tasks are reusable entities.

### C) Task Detail

Purpose: complete content review/edit surface for reusable task.

- Header: title, domain, status chip.
- Sticky top-right actions.
- Review actions preserved from existing behavior:
  - Approve
  - Return with comments (mandatory free text)
- Content structure and backend behavior unchanged.

### D) Workflow Detail

Purpose: workflow review/edit with clear included task list.

- Header: title, domain, status chip.
- Sticky top-right actions.
- Review actions and behavior unchanged from existing system.
- Display included tasks clearly while preserving independent task reuse model.

## 3) Component Rules

- Cards: consistent spacing/radius/shadow/heading hierarchy.
- Chips: semantic color mapping only.
- Queue rows: consistent rhythm and clear click target.
- Rail: keyboard-accessible collapse/expand; persist preference.
- States required on key surfaces: loading, empty, error.
- Avoid ad-hoc one-off CSS patches; any temporary patch must be explicitly marked for removal.

## 4) Acceptance Checklist

- [ ] No review-flow behavior regressions vs current `main`
- [ ] Dashboard shows actionable-only scoped counts
- [ ] Review Queue is merged list with type badges and Open-only row action
- [ ] Reviewer sorting follows agreed priority order
- [ ] Return action enforces mandatory free-text comment
- [ ] Task/Workflow detail actions are sticky top-right
- [ ] Left rail supports expanded/collapsed modes
- [ ] Desktop view meets 4-column card density target
- [ ] Visual consistency across queue + detail surfaces
- [ ] Keyboard navigation + visible focus states on core controls

## 5) Notes / Open Items

- Dashboard remains intentionally lightweight in v1.
- Dark mode intentionally deferred.
- If backend lacks direct task-side blocker flag, derive priority from workflow-side signal.
