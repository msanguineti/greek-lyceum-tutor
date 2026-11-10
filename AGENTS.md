# Greek Lyceum Tutor — repository guidance

Git is the development source of truth for four Greek-language tutors for Γ΄ ΓΕΛ / Πανελλαδικές 2027. All twelve authoring skills live under `skills/`; each built tutor contains exactly six. The repository root is authoring source, not an installable four-field plugin. The published marketplace at `.agents/plugins/marketplace.json` points to four complete generated packages under `plugins/`.

## Orientation and authority

Read [design](docs/design.md) and [current content and limits](docs/status.md) before changes. Use [development](docs/development.md) for actual check/build commands, [programme](docs/programme.md) for product scope and roadmap, and `distribution/products.json` for exact field inventories, names, versions and readiness gates.

Read ignored `.dev/PROJECT.md` for accepted project decisions and local repository policy, and `.dev/phase.md` for the current assignment, checks and unresolved work. Reuse these records; do not create per-chat handoffs. If private records are missing, recover supported facts from requirements, Git, source and tests without inventing approvals or prior verification. Private records do not automatically follow another clone or host.

Use relevant installed engineering skills and available general consultant/reviewer roles when useful. The tutor skills are product source; they do not change the development agent's role or conversation language. Apply proportionate independent review and checks; do not create a programme phase for routine maintenance. Explicit programme phases require distinct technical and acceptance reviews and initiator closure.

## Product constraints

- Preserve six independently invocable skills per field, the existing 2nd-field technical identity/names, and field-specific namespaces and subject selection. Shared source changes must reach every affected package.
- Hint-first is the default for every subject. Check the actual work internally, give focused graduated help, respect requested brevity/marking, and provide full solutions when explicitly requested. Student-facing text and human documentation are Greek.
- The reviewed official 2027 maps and detailed exclusions govern. Unknown scope is not included; prior-year or graduation syllabuses are not substitutes. Every subject needs its own reviewed map and source provenance.
- Textbooks, exam papers and full IEP guides stay link-only. Never add their PDFs, extracted texts, copied questions or answer keys without explicit redistribution permission. Preserve only the six registered administrative originals and their provenance/hashes. A locator is not access to its source.
- Runtime stays skills-only: no backend, MCP, hooks, repository access, local executor, stored student progress or desktop-only requirement. Preserve human-facing source-access and capability limitations.
- No student conversations, personal progress or private plugin/workspace/release identifiers in Git or distribution. No raw trials, screenshots, diagnostics or generated archives in the working tree. Use disposable synthetic check material outside it.

## Verification and delivery

Use Python 3 and the pinned `requirements-dev.txt` dependency, or an available bundled runtime. Packaging/layout changes require `scripts/validate.py`, both regression scripts listed in [test guidance](tests/README.md), and candidate builds of all four fields into a disposable directory. Keep strict emitted-runtime closure distinct from the twelve-skill authoring tree. For a behaviour-preserving refactor, compare all four emitted payloads before/after. After source or human-guide edits, run `python3 scripts/marketplace.py` and `python3 scripts/marketplace.py --check`; never edit generated `plugins/` copies directly.

Instruction changes require relevant real-host checks when authorized. Structural success and subagent simulations never establish ChatGPT behaviour. Live tests use Temporary chats and verified plugin/version/model/settings; check actually loaded instructions when staleness matters.

Keep user/developer docs concise and written for their readers. Put internal direction, local choices, detailed plans and review/check state only in ignored `.dev/`. Do not add an internal public manual or duplicate available personal roles. Recheck [official packaging guidance](https://developers.openai.com/plugins/build/plugins) when changing manifest or marketplace conventions.

Own delegated file boundaries and serialize Git index/commit operations. Commit verified, reviewed source work on the permitted branch; inspect the staged diff and remaining status. Push, merge and release require covering authority; project adoption alone grants none. Do not rewrite history or change host/global configuration as setup.

## Distribution boundaries

Publication, readiness changes, marketplace activation, workspace-wide installation and shared production updates require explicit covering authority; source-work authority alone is insufficient. Existing plugin identity and audience must be preserved when an update is explicitly authorized; new field test copies remain owner-private.

Build archives contain the selected plugin runtime, licenses and intended human guides, not development scripts, tests, agent instructions or private records. A marketplace catalog must resolve to actual assembled plugin sources; do not advertise the authoring root or missing generated paths as an installable tutor.
