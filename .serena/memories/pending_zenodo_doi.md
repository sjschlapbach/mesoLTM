# Pending: register a Zenodo DOI and fill every placeholder

`mesoltm` has **no DOI yet**. When one is registered for a release, update **all**
the locations below so the repository is citable consistently. This memory is the
single source of truth for those locations — **delete it once the DOI is applied
everywhere.** (Pointer to this list lives in `CLAUDE.md` → "Pending follow-ups".)

## How to get the DOI
Enable the **GitHub–Zenodo integration** for the repo, then cut a GitHub Release
(a `v*.*.*` tag — the `release.yml` workflow creates the Release). Zenodo archives
that release and mints a versioned DOI plus a concept ("all-versions") DOI. Use the
**concept DOI** in the citation metadata unless you deliberately want to pin a
specific release version.

## Locations to update (checklist)

1. **`CITATION.cff`** (repo root) — uncomment/fill the `# doi: 10.5281/zenodo.XXXXXXX`
   line (currently commented, ~line 33) and remove the surrounding TODO comment.
   This is the machine-readable master; keep the `version:` field in step with the
   released version.
2. **`docs/about/citation.md`** — three spots:
   (a) the `!!! warning "DOI pending — placeholder citation"` admonition (replace it
   with the real DOI, e.g. a normal note or a DOI badge),
   (b) the repository `@software{...}` BibTeX `note = {TODO: DOI pending ...}` →
   replace with a real `doi = {...}` field,
   (c) the plain-text repository citation above the BibTeX (add the DOI).
3. **`docs/index.md`** — the Home "Citing mesoLTM" callout (`A DOI is **not yet
   registered**`) — update the wording once it exists.
4. **`ai-docs/index.md`** — the "## Citation" section: the `TODO: a DOI has not yet
   been registered` line and the `@software{...}` BibTeX `note = {TODO: DOI
   pending ...}` → real `doi`.
5. **`README.md`** — the "## Attribution and citation" section (~lines 212–227)
   currently references `CITATION.cff` and cites the paper but has **no DOI line for
   the repository itself**; add the DOI (and optionally a Zenodo DOI badge near the
   top).

## Verify after updating
- `cffconvert --validate` (if installed) or a YAML parse of `CITATION.cff`.
- `mkdocs build --strict` (docs pages).
- `grep -rniE "zenodo|doi pending|todo.*doi|not yet.*regist" README.md CITATION.cff docs ai-docs`
  returns nothing (excluding the paper DOI `10.1016/j.simpat...`).
- Then **delete this memory**.
