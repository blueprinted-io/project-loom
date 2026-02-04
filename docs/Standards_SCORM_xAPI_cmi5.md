# SCORM, xAPI, and cmi5 — What They Actually Are

_Source: adapted from the `blueprinted-io/documentation` repository. Included here as context: delivery standards matter, but they are not the foundation. The foundation is the governed Task/Workflow model._

## The short version

- **SCORM**: packaging + basic tracking inside an LMS. Widely supported, limited.
- **xAPI (Tin Can)**: flexible event statements. Powerful but unopinionated; you must define structure.
- **cmi5**: a profile of xAPI that reintroduces launch and structure (closer to a SCORM successor).

The core constraint is rarely technical; it’s cultural and operational: most organizations still design content as monolithic courses and measure completion, regardless of protocol.

---

## Why this matters to blueprinted.io

blueprinted.io treats protocols as **last-mile export formats**.

The canonical source of truth is a governed, versioned definition of work:

- **Tasks**: atomic outcomes with facts, concepts, dependencies, and verifiable steps.
- **Workflows**: ordered compositions of tasks that produce an objective.

From that source, outputs can be rendered to:

- Markdown / PDF
- Web views
- JSON
- (future) SCORM / cmi5 / xAPI

The protocol should not constrain how work is defined.
