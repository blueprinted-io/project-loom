# README

## Executive Summary

This repository contains the **blueprinted.io** Learning Content System: a database-defined approach to procedural learning content.

If you want to run the prototype locally right now, jump to **Quickstart (Run Locally)** below.

This system exists to stop procedural learning content from drifting, contradicting itself, and becoming unreliable.

It does this by defining work as structured data, not documents.

Instead of writing guides, courses, and videos separately, it defines **Tasks** and **Workflows** as canonical records. Every learning format is derived from those records. If the task is correct, everything built from it is correct. If it is wrong, it is wrong once and can be fixed once.

This is a system for accuracy, reuse, and trust.  
It is not a teaching philosophy.

For system structure and schema details, see [Learning Content System Design](docs/Learning_Content_System_Design.md).  
For standards, governance, and review rules, see [Learning Content Governance](docs/Learning_Content_Governance.md).

---

## The Problem This Solves

If you work in a technical environment, you have probably seen this:

- Multiple documents describing the same process differently  
- “Completed training” that does not translate into capability  
- Content that rots the moment a product or system changes  
- SMEs rewriting the same steps repeatedly  
- No clear source of truth for how work is actually done  

These are not delivery problems.  
They are structural problems.

This system addresses the structure.

---

## What This System Is

This is a **database-defined learning content system**.

It defines:

- **Tasks** as atomic units of real work  
- **Workflows** as ordered compositions of tasks that achieve an objective  

Tasks and workflows are stored as structured records, versioned, reviewed, and governed. All learner-facing materials are assembled from this data, not authored independently.  
The data model and schema are specified in [Learning Content System Design](docs/Learning_Content_System_Design.md), and the governance rules are defined in [Learning Content Governance](docs/Learning_Content_Governance.md).

---

## What a Task Is

A **Task** represents one atomic outcome a person can produce.

A task always defines:

- the outcome  
- the facts required beforehand  
- the concepts required to understand the work  
- the exact steps to perform  
- the dependencies that must already be satisfied  

Every step is explicit, executable, and verifiable.  
If you cannot observe whether a step or outcome occurred, it is not a valid task.

Tasks are reusable and may appear in multiple workflows.

---

## What a Workflow Is

A **Workflow** represents a composite outcome produced by executing multiple tasks in order.

Workflows:

- contain tasks only, never procedural steps  
- have a single, organization-defined objective  
- reference only confirmed task versions  
- do not define prerequisites or learning sequences  

Any condition that must already be true is declared at the task level. This prevents duplication, contradiction, and drift over time.

---

## What This System Is Not

This system is deliberately not many things.

It is not:

- a course platform  
- a learning experience design framework  
- a mastery or expertise engine  
- a troubleshooting or diagnostics system  
- a break-and-fix environment  

Those capabilities are real, valuable, and necessary.  
They simply do not belong here.

This system defines **safe, repeatable, correct execution**.  
It establishes what “good” looks like and makes that definition stable.

Everything else belongs in the domain of **experience**.

That includes:

- hands-on experimentation  
- labs and sandboxes  
- observed or coached task execution  
- supervised practice  
- real workload assignments  
- failure, recovery, and problem-solving  

People do not develop mastery by reading procedures.  
They develop mastery by doing the work, making mistakes, and correcting them in environments where failure is safe.

This system exists to ensure that when someone starts experimenting, they already know what correct execution looks like.

It is a foundation, not a substitute for experience.

---

## A Note on Mastery

This system is not designed to produce mastery.

At this level, the purpose of work is not mastery.  
The purpose of work is to **create the conditions under which mastery can develop**.

Those conditions include:

- a clear definition of correct execution  
- repeatable, verifiable outcomes  
- shared understanding of what “good” looks like  
- freedom to practice without ambiguity  

Mastery emerges later, through experience, repetition, and exposure to real variation. It cannot be reliably authored, versioned, or governed as content.

This system provides the stable ground from which people can safely move beyond it.

---

## Why Governance Is Strict

Tasks and workflows are not documentation.  
They are authoritative definitions.

Because of that:

- all records are versioned  
- confirmed records are immutable  
- human review is mandatory  
- draft or submitted tasks cannot appear in workflows  
- changes are explicit and auditable  

This prevents silent meaning changes and ensures that derived materials remain trustworthy over time.

Full governance and review requirements are defined in [Learning Content Governance](docs/Learning_Content_Governance.md). The record lifecycle, validation, and schema structure are defined in [Learning Content System Design](docs/Learning_Content_System_Design.md).

---

## Who This Is For

This system is for people who are adjacent to learning but responsible for real outcomes:

- engineers and architects  
- SMEs who own procedures  
- learning teams who need content that does not drift  
- organizations that care whether people can actually do the work  

If you have ever said “the guide says one thing and reality says another”, this system is aimed at you.

---

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

## Quickstart (Run Locally)

The runnable MVP lives in `lcs_mvp/`.

```bash
cd lcs_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open: http://127.0.0.1:8000

### Seed the Debian demo dataset

```bash
cd lcs_mvp
source .venv/bin/activate
python3 seed/seed_debian_corpus.py --reset-db
```

### Switch between demo and blank database (admin)

Switch your role to `admin` in the UI, then open:

- http://127.0.0.1:8000/db

### Roles (prototype)

Cookie-based role switching (not real auth):

- `viewer` / `author` / `reviewer`: normal app roles (no audit log)
- `audit`: read-only access, includes audit log
- `admin`: can see everything; can force submit/confirm (recorded in audit)

---

## In Short

- Work is defined once, correctly.
- Tasks are the atomic unit.
- Workflows compose tasks into outcomes.
- Everything else is derived.
- Human review is non-optional.
- Drift is treated as a structural failure, not a training issue.

That is the entire point.
