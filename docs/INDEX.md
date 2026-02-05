# Documentation Index

This repo uses docs as the system contract.

Purpose of this file: make it fast to answer:
- what each document is for,
- whether it is implemented,
- and where to look next.

## Core (current contract)

- [Statement of Intent](Statement_of_Intent.md)
  - Why the system exists and the non-negotiable posture.
  - Status: active.

- [Learning Content Governance](Learning_Content_Governance.md)
  - The standards: how Tasks/Workflows/Steps must be written and reviewed.
  - Status: active.

- [Learning Content System Design](Learning_Content_System_Design.md)
  - MVP implementation-oriented model notes and constraints.
  - Status: active.

## Vision (not implemented / future-state)

- [Output and Delivery Vision](Output_and_Delivery_Vision.md)
  - How confirmed records become outputs safely (renderer + provenance + “no new steps”).
  - Status: vision.

- [Interactive Delivery: H5P/SCORM](Interactive_Delivery_H5P_SCORM.md)
  - Provisional exploration of interactive packaging and tracking.
  - Status: exploration.

- [Standards: SCORM/xAPI/cmi5](Standards_SCORM_xAPI_cmi5.md)
  - Background and constraints for packaging/tracking standards.
  - Status: reference.

- [LearningOps](LearningOps.md)
  - Operating model for maintaining content as a governed system.
  - Status: reference.

## Drafts (partially implemented)

- [Auth and Domains (Draft)](Auth_and_Domains_Draft.md)
  - Domain vs tags distinction and auth direction.
  - Status: partially implemented in `lcs_mvp` (local auth + domain registry/entitlements).

- [Gamification Achievements (Draft)](Gamification_Achievements_Draft.md)
  - Untappd-style achievements for author/reviewer roles; no leaderboards by default.
  - Status: draft (not implemented).

- [Applicability and Compatibility (Draft)](Applicability_and_Compatibility_Draft.md)
  - Compatibility constraints separate from domain/tags.
  - Status: draft (not implemented).

## Working agreement

- This index is allowed to be short. It should point to the truth, not duplicate it.
