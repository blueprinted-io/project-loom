# blueprinted.io --- Governed Operational Knowledge Infrastructure

## Executive Summary

blueprinted.io is a database-defined system for governing operational
knowledge.

It defines work as structured, versioned task records with enforced
review and confirmation boundaries.

The goal is simple:

One official version of how work is done.\
Used by both people and AI.

This is not a documentation tool.\
It is an operational truth layer.

------------------------------------------------------------------------

## Why

AI systems are increasingly embedded in operational workflows.

They generate instructions, suggest configuration changes, and influence
decision paths.

AI does not automatically check your organisation's approved process.

It predicts answers based on patterns.

If your operational knowledge is fragmented, outdated, or inconsistently
maintained, AI will amplify that inconsistency.

Most organisations do not have:

-   A single confirmed version of each operational task\
-   Enforced review before instructions become authoritative\
-   Immutable version history\
-   Clear traceability of which version was relied upon

blueprinted.io defines that missing layer.

------------------------------------------------------------------------

## Core Principles

### 1. Tasks are structured units of operational work

Work is decomposed into discrete, outcome-based task records.

Each task contains:

-   Required facts\
-   Conceptual understanding\
-   Procedure\
-   Dependencies

Tasks are versioned.

------------------------------------------------------------------------

### 2. Confirmation defines authority

AI can assist in drafting or updating tasks.

Draft content is not official.

A task becomes authoritative only after human confirmation.

If it has not been confirmed, it is not official.

------------------------------------------------------------------------

### 3. Version history is preserved

Changes create new versions.

Previous versions are retained.

Silent overwrite is not permitted.

This enables traceability and auditability.

------------------------------------------------------------------------

### 4. Humans and AI reference the same confirmed layer

The system is designed so that:

-   Humans perform tasks using confirmed records\
-   AI systems reference the same confirmed records\
-   There is no separate "AI knowledge" path

This creates alignment between automation and accountability.

------------------------------------------------------------------------

## LearningOps Context

The project originated in learning operations.

Traditional learning content is built like waterfall software:

-   Large releases\
-   Slow review cycles\
-   Drift between documentation and reality

LearningOps proposes:

-   Atomic task units\
-   Version control\
-   Continuous review\
-   Composable workflows\
-   Auditability

blueprinted.io implements these principles structurally.

See: docs/LearningOps.md

------------------------------------------------------------------------

## Why This Is Non-Trivial

Defining an official task layer requires:

-   Decomposing real work into structured units\
-   Separating instruction from commentary\
-   Managing dependencies between tasks\
-   Enforcing review boundaries\
-   Preserving version history without friction\
-   Designing workflows that teams will actually use

This is infrastructure design, not content formatting.

------------------------------------------------------------------------

## Live Demo

https://blueprinted-io-mvp.blueprinted.io/login

------------------------------------------------------------------------

## Quickstart (Run Locally)

The runnable MVP lives in `lcs_mvp/`.

cd lcs_mvp\
python3 -m venv .venv\
source .venv/bin/activate\
pip install -r requirements.txt\
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Open: http://127.0.0.1:8000

------------------------------------------------------------------------

### Seed the Debian demo dataset

cd lcs_mvp\
source .venv/bin/activate\
python3 seed/seed_debian_corpus.py --reset-db

------------------------------------------------------------------------

### Switch between demo and blank database (admin)

Switch your role to `admin` in the UI, then open:

http://127.0.0.1:8000/db

------------------------------------------------------------------------

## Roles (prototype)

Cookie-based role switching (not production authentication):

-   viewer / author / reviewer: normal roles\
-   audit: read-only, includes audit log\
-   admin: full visibility; can force submit or confirm (recorded in
    audit)

------------------------------------------------------------------------

## Documentation

-   docs/Statement_of_Intent.md\
-   docs/LearningOps.md\
-   docs/Learning_Content_System_Design.md\
-   docs/Learning_Content_Governance.md\
-   docs/Standards_SCORM_xAPI_cmi5.md\
-   docs/Auth_and_Domains_Draft.md

------------------------------------------------------------------------

## License

Apache License 2.0. See LICENSE and NOTICE.
