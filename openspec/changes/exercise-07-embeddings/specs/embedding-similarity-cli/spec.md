## ADDED Requirements

### Requirement: Command-line embedding comparison
The repository SHALL provide `scripts/compare.py`, accepting required `--text-a` and
`--text-b` arguments. The command MUST reuse `OpenAIEmbedder` to embed both inputs
and print both supplied texts and their cosine similarity, calculated only with the
Python standard library.

#### Scenario: Comparing two texts
- **WHEN** a user runs `python scripts/compare.py --text-a "first text" --text-b
  "second text"` with a valid OpenAI API key
- **THEN** the command prints the two texts and their numeric cosine similarity

### Requirement: Reproducible sanity-check record
The repository SHALL include `app/embedding_pipeline/SANITY_CHECK.md` containing the
numeric results for the prescribed semantically close, unrelated, and generic text
pairs, plus a three-to-five-line interpretation of the results. The README MUST
document running the CLI both inside the Docker service and locally with `uv`.

#### Scenario: Reviewing exercise evidence
- **WHEN** an instructor opens the sanity-check document and README
- **THEN** they can see all three recorded comparisons and commands to reproduce the
  CLI in Docker and local environments
