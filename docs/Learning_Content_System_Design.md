# Learning Content System Design

This document defines the data model, schema, and system structure for
database-defined learning content. It complements
`Learning_Content_Governance.md`, which covers standards, governance,
and review rules.

# Learning Content Standards (Database‑Defined)

## Purpose

Learning content is database‑defined. The database records form the
canonical, learner‑facing source of truth for all procedural learning.
All delivery methods; written guides, videos, interactive walkthroughs,
live labs, ILT, job aids, SCORM, derive from these database definitions
for accuracy and structure.

A data‑defined record provides:

1.  **Outcome** – the title stated as a verb-driven outcome.

2.  **Facts** – literal information the learner must know beforehand.

3.  **Concepts** – the mental models required to understand why the
    steps work.

4.  **Procedure** – the named sequence of steps that perform the task.

5.  **Dependencies** – prerequisites that must already be true or
    completed.

Steps are stored as a Steps array within the Procedure.

A workflow record provides:

1.  **Objective** – the measurable outcome defined by the organization.

2.  **Prerequisites** – required tasks or conditions.

3.  **Tasks** – ordered task references that produce the objective.

If a task or workflow record is wrong, every derived learning format
becomes wrong. Tasks and workflows are not internal documentation. They
are the foundation upon which all learning experiences are built.

## Core Entities

### Task

A Task represents one atomic outcome.

It defines the procedure required to complete a single action sequence.

- A task produces one outcome.

- The procedure is composed of ordered Steps.

- Each step is written in imperative form.

- A task is self‑contained — all execution detail is defined in its
  record.

- Tasks are reusable components that can be referenced by multiple
  workflows.

### Workflow

A Workflow represents a composite outcome made of multiple tasks.

It defines how tasks combine to produce a larger result.

- A workflow consists of ordered Task references, not procedural steps.

- Each task listed is required to produce the workflow objective.

- Workflows link directly to the relevant tasks for execution detail.

- The workflow objective is defined by the organization, not by content
  writers.

### Data Schema Relationships

| Entity | Contains | Term Used | Description |
|----|----|----|----|
| Task | Procedure (Steps) | Steps | Ordered atomic instructions needed to perform one outcome |
| Workflow | Tasks | Tasks | Ordered sequence of tasks that together produce a single workflow objective |

### Required Fields

Each entity must define the following data fields:

#### Task

1.  Title – clear learner‑facing name

2.  Outcome – description of the result of the task

3.  Facts – literal information required to execute the task

4.  Concepts – minimal mental models required to execute the task

5.  Procedure – named sequence of steps (Steps array)

6.  Dependencies – required prior knowledge, skills, or conditions

7.  Irreversible flag – required if the task cannot be undone

#### Workflow

1.  Title – clear learner‑facing name

2.  Objective – organization-defined outcome for the workflow

3.  Prerequisites – required tasks or conditions

4.  Tasks – ordered list of task references

### Style Rules

- Direct sentences

- Imperative verbs

- No figurative language

- Consistent terminology

- Each step must describe a single, clear operation

### Rich Media

Screenshots and other rich media are linked media assets used only when
text cannot be made unambiguous. They are referenced at the step
level, not stored inline and are to be stored as linked URLs.
Assets may point to the internal asset library or approved external
platforms (graphics, video, audio, Storylane modules, Rise modules,
and hosted video platforms).

### Error Prevention

- Tasks that include irreversible changes must be flagged at the task
  level.

- Troubleshooting content is not permitted within task or workflow
  steps.

### Quality Gate

Automated validation logic ensures structural integrity:

- Workflow: tasks only (no steps)

- Task: steps only (no tasks)

- Imperative language is enforced at the step level

- Terminology consistency is verified across all entities

- Circular dependencies and self-references are blocked

### Structure

Tasks and Workflows together form the hierarchical learning content
graph.

- Tasks are atomic, reusable units.

- Workflows are ordered compositions of tasks.

- All learner‑facing materials are assembled dynamically from this data.

This structure enables automation, version control, advanced analytics,
and AI‑driven content generation, while preserving the clear,
authoritative standards that underpin all learning experiences.

# Database Model

## Atomic Ownership of Knowledge and Procedure

Each Task record is self‑contained and owns its own knowledge, facts,
and procedural data.

These elements are stored as arrays within the Task record and are not
shared between Tasks to preserve canonical accuracy. The Workflow
Database provides structure and sequencing without redefining procedure.

Assessment, Governance, and Delivery databases are defined conceptually
but excluded from MVP scope. These will be introduced in later phases
once core content integrity and authoring workflows are stable.

<table style="width:100%;">
<colgroup>
<col style="width: 23%" />
<col style="width: 41%" />
<col style="width: 35%" />
</colgroup>
<thead>
<tr>
<th>Database</th>
<th>Purpose</th>
<th>Notes</th>
</tr>
</thead>
<tbody>
<tr>
<td>Task (Master) DB</td>
<td>Canonical source of all atomic Task records. Each record defines one
outcome and the full procedure required to achieve it.</td>
<td><ul>
<li><p>Core of the architecture.</p></li>
<li><p>Contains all <strong>Facts</strong>, <strong>Concepts</strong>,
and <strong>Procedure (Steps)</strong> as arrays within each
record.</p></li>
<li><p>These elements are <strong>not shared</strong> between Tasks;
each Task owns its own knowledge and procedure.</p></li>
</ul></td>
</tr>
<tr>
<td>Workflow DB</td>
<td>Defines named workflows as ordered sequences of Task IDs. Provides
structure for composite objectives.</td>
<td><ul>
<li><p>References Tasks by ID only; contains <strong>no procedural
detail</strong>.</p></li>
<li><p>Enables composite learning paths without duplicating Task
data.</p></li>
<li><p>Workflows contain tasks only.</p></li>
</ul></td>
</tr>
<tr>
<td>Asset DB</td>
<td>Stores or references rich media (screenshots, diagrams, videos) used
within Tasks or Workflows.</td>
<td><ul>
<li><p>Media stored as linked URLs or file IDs (not inline).</p></li>
<li><p>Tasks and Workflows reference assets by ID.</p></li>
<li><p>Links to the asset library and approved external platforms.</p></li>
<li><p>Supports language localization and asset versioning.</p></li>
</ul></td>
</tr>
<tr>
<td>Assessment DB</td>
<td>Defines internal learning checks, questions, and rubrics for
non‑certified learning.</td>
<td><ul>
<li><p><strong>Planned for future implementation (not
MVP).</strong></p></li>
<li><p>Certification data remains external.</p></li>
<li><p>Will link to Tasks and Workflows once internal assessment
features are required.</p></li>
<li><p>Future intent: build question banks using database content as
source data for AI.</p></li>
</ul></td>
</tr>
<tr>
<td>Governance / Validation DB</td>
<td>Houses quality rules, style guides, ownership metadata, and version
control.</td>
<td><ul>
<li><p><strong>Planned for future implementation (not
MVP).</strong></p></li>
<li><p>Will manage automated validation such as imperative‑language
checks, terminology checks, and version history.</p></li>
</ul></td>
</tr>
<tr>
<td>Delivery / Publishing DB</td>
<td>Assembles learner‑facing outputs (written guides, videos, SCORM,
etc.) from canonical data.</td>
<td><ul>
<li><p><strong>Planned for future implementation (not
MVP).</strong></p></li>
<li><p>Pulls from Task, Workflow, and Asset DBs.</p></li>
<li><p>Supports localization, rendering, and publication
tracking.</p></li>
</ul></td>
</tr>
</tbody>
</table>

# Schema Definition

## Purpose

This section defines the schema for database‑defined learning content.
Each database represents a distinct domain of governance, collectively
forming the Learning Content Ecosystem. All domains operate on shared
principles of accuracy, hierarchy, and traceability. Learning content is
managed as structured data rather than written documents.

## Databases

| Database | Purpose | Core Entities |
|----|----|----|
| Task (Master) DB | Canonical source of all atomic Task records. Each record defines one outcome and the full procedure required to achieve it. | Task, Procedure, Step, Dependency |
| Workflow DB | Defines named workflows as ordered sequences of Task IDs. Establishes how Tasks combine to produce composite objectives. | Workflow, TaskReference, Prerequisite |
| Asset DB | Stores or references rich media assets (screenshots, diagrams, videos) used within Tasks or Workflows. | Asset, MediaType, UsageContext, Locale, Version |
| Assessment DB | Defines internal learning checks and evaluations for non‑certified learning. | Assessment, Question, Rubric, Result |
| Governance / Validation DB | Houses quality rules, style guides, ownership metadata, and version control. | StyleRule, QualityRule, Owner, Version |
| Delivery / Publishing DB | Assembles learner‑facing outputs (written guides, videos, SCORM, etc.) from canonical data. | GuideInstance, Format, Locale, VersionHistory |

External certification systems remain outside this model. They may
reference learning content through metadata only.

**MVP Note:**  
The **Assessment**, **Governance**, and **Delivery** databases are
defined conceptually but excluded from MVP scope. They will be
implemented in later phases once core content integrity and authoring
workflows are stable.

## Database Separation

The Learning Content Ecosystem separates atomic and composite
definitions:

- The Task (Master) Database contains all atomic Task records. Each
  record is self‑contained and owns its own knowledge, facts,
  concepts, and procedural data. These components are not shared between
  Tasks, ensuring accuracy.

- The Workflow Database defines named workflows as ordered sequences of
  Task IDs. Workflows provide structure and context but contain no
  procedural detail.

This separation ensures Tasks remain reusable and authoritative, while
Workflows provide compositional flexibility.

## Structural Relationships

1.  **Tasks are atomic and self‑contained.**  
    Each Task defines its own facts, concepts, procedure, and outcome.

2.  **Workflows reference Tasks.  **
    A Workflow record contains ordered Task IDs.  
    Workflows contain tasks only.

3.  **Assets support Tasks and Workflows.  **
    Tasks and Workflows link to media assets by ID for clarity and
    reinforcement.

4.  **Governance rules apply globally.  **
    Quality gates, style rules, and validation logic are applied across
    all databases.

5.  **Delivery draws from master data.  **
    Learner‑facing materials are dynamically assembled from Task and
    Workflow data.

## Validation and Quality Governance

- Imperative Language Enforcement: Each Step within a Task must use
  imperative verbs.

- Terminology Consistency: All entities follow defined terminology from
  the governance framework.

- Structural Integrity: Tasks contain only Steps. Workflows contain
  only Tasks (no direct Steps). Circular dependencies and
  self-references are blocked.

- Error Prevention: Irreversible tasks are flagged at the task level.
  Troubleshooting content is excluded from steps.

- Validation Split: Structural and terminology checks are automated;
  correctness is confirmed by human review.

## Data Hierarchy Diagram (Conceptual)

Task (Facts, Concepts, Procedure/Steps) → Workflow (Objective) → Guide → Delivery  
↓  
Governance ← Asset

This hierarchy represents both data lineage and learning dependency.
Tasks define what must be done. Workflows define how tasks combine to
achieve an objective. Guides form the learner-facing expression.
Governance ensures integrity. Assessment is a future layer and is out of
scope for MVP.

## Extensibility

The schema is designed for modularity. New databases or entities may be
introduced as learning domains evolve, provided they conform to
governance principles: Canonical data derives from defined sources;
Relationships are explicit and validated; Terminology remains consistent
with the Learning Content Governance standard.

## Summary

The database-defined schema transforms learning content into a
structured, verifiable ecosystem. Tasks and Workflows no longer exist as
isolated written guides; they are interrelated data objects governed by
shared standards. This structure supports automation, maintenance,
analytics, and AI-assisted content generation—all while preserving the
clarity and intent of the original governance framework.
