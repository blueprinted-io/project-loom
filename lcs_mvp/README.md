# Learning Content System MVP (Prototype)

Quick prototype implementing the core primitives from the provided docs:

- **Task** and **Workflow** as canonical, versioned records
- Status lifecycle: `draft → submitted → confirmed → deprecated`
- Confirmed records are immutable (edits create a new version)
- Workflows can reference **confirmed Task versions only**
- Simple warning-only step linting
- Export workflows to Markdown (HTML/PDF can be added next)

## Run

```powershell
cd C:\Users\ewan\.openclaw\workspace\lcs_mvp
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: http://127.0.0.1:8000

## Notes
- SQLite database is stored at `./data/lcs.db`.
- This is a prototype: auth/roles are simplified.
