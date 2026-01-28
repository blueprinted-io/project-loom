Work list: open questions + fixes required

Goal: enumerate what still needs an answer, a decision, or a fix to keep the model stable and enforceable.

1) Define the Objective layer (SOLVED)
- Problem: Post‑Condition ↔ Objective alignment requires Objective DB, but Objective DB is not defined.
- Needed: Objective entity schema, ownership, and how Objectives reference Facts (or not).
- Decision: Are Objectives first‑class records or embedded in Tasks/Workflows?
- Response (agreed direction):
  - Objective lives at Workflow level only and is org‑defined (not authored by content writers).
  - Task level uses Outcome to describe the atomic, observable state change produced by the task.
  - Post‑Condition is treated as a synonym for Task Outcome and should be deprecated to reduce drift.
  - Workflow Objective is the canonical “Objective” term; Task Outcome must map to it via workflow composition.
  - MVP decision: no Objective DB. Objective is a required field in Workflow records.
  - Future stance: no Objective DB anticipated, since objectives should not be reused by definition.

2) Unify Task/Workflow schemas (SOLVED)
- Problem: “Required Structure” vs “Required Fields” conflict.
- Needed: One canonical schema per entity, with a mapping table for legacy text.
- Decision: Which field names are authoritative (Outcome vs Expected Outcome vs Post‑Condition)?
- Response (agreed direction):
  - Task canonical fields: Title, Outcome, Facts, Concepts, Procedure, Dependencies.
  - Procedure contains Steps[] (Steps are the only term for atomic actions).
  - Workflow canonical fields: Title, Objective, Prerequisites, Tasks.
  - Expected Outcome and Post‑Condition are removed; Outcome/Objective are the only outcome fields.
  - Terminology: use “Steps” (not Actions) everywhere; tasks contain Steps, workflows contain Tasks.

3) Resolve “self‑contained tasks” vs shared knowledge (SOLVED)
- Problem: Tasks are said to own Facts/Concepts, but later Facts/Objectives look shared.
- Needed: Explicit rule: no sharing, or controlled sharing with a canonical Fact/Concept registry.
- Decision: Are Facts entities or arrays inside Task only?
- Response (agreed direction):
  - Zero sharing. Facts, Concepts, and Steps/Procedure are owned by the Task record only.
  - No shared Fact/Concept registry; no reuse across Tasks.
  - Add a note to identify and fix the exact document section(s) that imply shared Facts/Objectives.

Resolution plan for document cleanup (agreed)
- Objective vs Outcome: Objective belongs to Workflow; Outcome belongs to Task.
- Remove Objective DB and Post‑Condition mapping logic.
- Normalize schema tables to remove Fact/Concept as standalone entities.
- Fix data hierarchy diagram to show Task (Facts/Concepts/Steps) → Workflow (Objective).
- Enforce strict non‑sharing; only Task reuse across Workflows is allowed.
- Update validation rules to roll Task Outcomes up to Workflow Objective.

4) Enforce workflow composition rules (SOLVED)
- Problem: “Workflows may be nested” contradicts “tasks only.”
- Needed: Remove nesting or define a separate “Program/Initiative” layer for large transformations.
- Decision: Final stance: workflows contain tasks only.
- Response (agreed direction):
  - Workflow nesting is removed. Workflows cannot contain workflows.
  - Reuse Tasks across multiple Workflows as needed.

5) Step model for conditional/variant procedures (SOLVED)
- Problem: “No conditional logic in steps” breaks real workflows with environmental variance.
- Needed: Approved mechanism (variants, precondition gating, decision tables, or explicit exclusions).
- Decision: How to represent forks without violating atomicity.
- Response (agreed direction):
  - No conditional steps inside Tasks.
  - Variants are expressed at the Workflow layer by composing Tasks.
  - Example: Workflow A omits the “Enable encryption” Task; Workflow B includes it.
  - Reuse shared Tasks; isolate variant behavior into distinct Tasks.

6) Troubleshooting and diagnostic content location (SOLVED)
- Problem: Troubleshooting is banned from steps but no alternative container exists.
- Needed: Define a separate “Troubleshooting/Diagnostics” content type or explicitly exclude from scope.
- Decision: In‑scope or out‑of‑scope, and where it lives.
- Response (agreed direction):
  - Out of scope. Troubleshooting and diagnostics are not part of the model.
  - Diagnostics is the application of fault isolation using the capability to complete tasks/workflows.
  - Teaching fault isolation is excluded; teaching workflow capabilities is in scope.

7) Governance and authority model (SOLVED)
- Problem: “Document is the contract,” but no owner/approval or exception process is defined.
- Needed: Who approves changes, how disputes are resolved, and how model evolution is recorded.
- Decision: Single owner vs committee; change control path.
- Response (agreed direction):
  - “Document is the contract” is outdated and will be removed.
  - Governance is record‑level: all records enter an unconfirmed state.
  - Human review is required to confirm records, regardless of whether the record was created by AI or by a human.
  - AI can assist with ingress, but approval is always human‑verified.

8) Versioning for MVP (SOLVED)
- Problem: Governance DB is excluded from MVP, but version control is mandated.
- Needed: Minimal MVP versioning mechanism and metadata fields.
- Decision: Where version data lives without Governance DB.
- Response (agreed direction):
  - Add minimal versioning fields to each Task/Workflow record: record_id, version, status, created_at, updated_at, created_by, updated_by, reviewed_by, reviewed_at, change_note.
  - Any edit creates a new version; only one version can be confirmed at a time.
  - All records start unconfirmed; only confirmed records are publishable.
  - Deprecate old confirmed versions; never delete.
  - Additional governance: an AI agent monitors R&D changelogs and flags affected Tasks/Workflows for review.

9) Irreversible action flagging (SOLVED)
- Problem: Rule exists but there is no schema field.
- Needed: Field definition at action level and validation rule.
- Decision: Flag placement (Action, Task, or both).
- Response (agreed direction):
  - Add an irreversible flag at the Task level (closest to the system change).

10) Media asset policy vs examples (SOLVED)
- Problem: Examples embed images inline despite policy requiring linked assets at action level.
- Needed: Update examples or loosen rule for documentation‑only visuals.
- Decision: Are example diagrams governed by Asset DB rules?
- Response (agreed direction):
  - Asset DB stores links to an asset library and other storage locations.
  - Example asset types: graphics, video, audio, Storylane modules, YouTube (and other platforms), Rise modules.

11) Terminology normalization (SOLVED)
- Problem: Terms drift (Facts vs Fact entity; Outcome vs Expected Outcome vs Post‑Condition).
- Needed: Canonical glossary and cross‑reference list.
- Decisions and remaining work:
  - Use “Steps” everywhere; remove “Actions” in schema and rules.
  - Facts and Concepts are arrays inside Tasks only (no Fact/Concept entities).
  - Remove Objective DB references and Objective‑Fact linkage from validation/diagrams.
  - Build a glossary section and ensure all expanded definitions match it.
  - Procedure is a named field inside Task and contains Steps[].
- Glossary (canonical terms):
  - Objective: Org-defined outcome at the Workflow level. Not authored by content writers.
  - Outcome: Atomic, observable state change produced by a Task.
  - Task: Smallest reusable unit of work that produces one Outcome.
  - Workflow: Ordered composition of Tasks that achieves one Objective.
  - Facts: Literal information required to execute a Task. Stored as an array in the Task.
  - Concepts: Minimal mental models required to execute a Task correctly. Stored as an array in the Task.
  - Procedure: The named sequence of Steps that executes a Task.
  - Steps: Atomic, imperative actions within a Procedure. Steps are the only term for actions.
  - Dependencies: Conditions or prerequisites that must be true before a Task can be executed.
  - Prerequisites: Conditions or Tasks that must be true/complete before a Workflow can be executed.

12) Scope boundary statement (SOLVED)
- Problem: Out‑of‑scope domains are implied but not explicit.
- Needed: Clear section stating procedural execution only; diagnostics/strategy excluded.
- Decision: Confirm and place near the front of the doc.
- Response (agreed direction):
  - Add an explicit Scope section near the top.
  - In scope: procedural execution, configuration, operational behaviors.
  - Out of scope: diagnostics/troubleshooting, strategic decisions, tool/architecture selection.

13) Assessment posture statement (SOLVED)
- Problem: Assessment is implied but deferred; creates ambiguity.
- Needed: Explicit “assessment deferred” statement and constraints.
- Decision: Define what is and is not implied by MVP.
- Response (agreed direction):
  - Assessment is deferred for MVP.
  - Future intent: build question banks and assessments using database content as source for AI.
  - Out of scope for now.

14) Quality gate enforcement mechanism (SOLVED)
- Problem: Rules are stated but enforcement mechanism is not defined.
- Needed: Validation pipeline or checklist for authoring.
- Decision: Automated vs manual enforcement for MVP.
- Response (agreed direction):
  - Automated validation handles structure and terminology.
  - Human reviewers are responsible for correctness and consequence.

15) Circular dependencies and prerequisites (SOLVED)
- Problem: No rule preventing task/workflow circular dependencies.
- Needed: Validation rule to prevent cycles and self‑reference.
- Decision: Where the rule is enforced (authoring tool vs governance DB).
- Response (agreed direction):
  - Add validation rules to block circular dependencies (Task A ↔ Task B) and self‑reference.

16) Single‑task workflows edge cases (SOLVED)
- Problem: Allows duplication with Tasks and can blur boundaries.
- Needed: Rule explaining when a single‑task workflow is allowed and why.
- Decision: Keep allowed, or require a higher‑level outcome justification.
- Response (agreed direction):
  - Single‑task workflows are valid and required when a single task achieves the workflow objective.

17) Formatting and editorial standards (SOLVED)
- Problem: Typos and mixed formatting reduce authority.
- Needed: Basic editorial pass and style rules.
- Decision: Minimum acceptable quality bar for governance docs.
- Response (agreed direction):
  - Editorial cleanup will be done at the end; AI-assisted passes are preferred.

18) Model evolution policy (SOLVED)
- Problem: “No special cases” principle stated but no operational rule exists.
- Needed: A formal change request path to evolve the model when edge cases arise.
- Decision: What qualifies as model change vs content exception.
- Response (agreed direction):
  - No content exceptions. If something does not fit, it triggers a model change request.
  - Change request includes: problem statement, affected records, proposed schema/rule change, migration impact.
  - Approval requires human review.
  - New model version is published; affected records are flagged for update.

19) Plain-language standard (SOLVED)
- Problem: Document is too technical for non‑specialist stakeholders.
- Needed: Define a lower reading level and enforce plain‑language style.
- Decision: Target reading level and style rules.
- Response (agreed direction):
  - Aim for a reading level around grade 9 or lower.
  - Use short sentences, simple words, and active voice.
  - Avoid jargon unless it is defined in the glossary.
