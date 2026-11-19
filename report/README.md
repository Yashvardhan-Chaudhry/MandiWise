# MandiWise IEEE report

`mandiwise.tex` is the implementation report: IEEEtran conference format, two columns. All figures except
the UI screenshots and the CEDA logo are drawn in TikZ/pgfplots inside the `.tex` file.

## Build

**Overleaf:** upload the whole `report/` folder, including `figures/`. Set the compiler to **pdfLaTeX**
(Menu → Compiler) and recompile.

**Locally:**

```bash
cd report
tectonic mandiwise.tex          # or: pdflatex mandiwise.tex  (run twice so references resolve)
```

The bibliography is inline (`thebibliography`), so no BibTeX run is needed. Packages: IEEEtran, cite,
amsmath/amssymb, graphicx, booktabs, array, multirow, url, xcolor, tikz, pgfplots, float, enumitem and
placeins. All of them ship with TeX Live and with Overleaf's default image.

## Figure files expected in `report/figures/`

A missing file does not break the build. The report shows a labelled "Screenshot pending" box instead,
or nothing in the case of the logo.

| File | Used in | Notes |
|---|---|---|
| `fig_ranking.png` | Ranking screen figure (Section X) | React client ranking result: breakdown, net range, price dates, PLACEHOLDER banner. If captured from the mock API, the caption must say so. |
| `fig_pool_detail.png` | Pooling trip detail figure (Section X) | Members, lifecycle state, cost split. |
| `ceda_logo.png` | Dispersion figure (Section V) | CEDA requires its logo on published visuals derived from its data. Shown bottom-right if present. |

Capture screenshots at 1600 px or wider in the light theme. They are scaled to column width. The other
screenshots named in `docs/handoff/SARTHAK_FRONTEND.md` (`fig_calculator.png`, `fig_i18n_hi.png`,
`fig_i18n_ur.png`) are not referenced. To add one, copy a `figure` block and call
`\screenshot{<file-stem>}{<description>}`.

## Test counts

Every test number in the report comes from macros at the top of `mandiwise.tex`: `\TestsRoot`,
`\TestsBackend`, `\TestsSkipped` and `\TestsTotal`, plus one per-file macro for each backend test file.
Change them there and nowhere else. They currently hold the counts measured on 2026-11-19 on PR #1:
backend 78 passed and 1 skipped, root 5.

## Open `TODO(yash)` markers

Search for `TODO(yash)` in `mandiwise.tex`. All of them are LaTeX comments, so none appears in the PDF.

1. **Test-count macros (2 markers, preamble).** These are the values measured on PR #1. Re-measure if
   anything else merges first, and re-check the per-file split on `main`.
2. **CEDA logo (Section V, after the dispersion figure).** Add `figures/ceda_logo.png`.
3. **Ranking screenshot caption (Section X).** If `fig_ranking.png` came from the mock API, say so in
   the caption.
4. **React client status (Section X).** Confirm the client's status and screenshots before submission.
   Keep the "being built / in progress" wording unless the client is merged and working.

## Number discipline

Every figure in the report is taken from a committed source: `research/findings.md`,
`research/engine_benchmark.md`, `research/commodity_aliases.md`, `docs/DECISIONS.md`,
`docs/transport/DEMO_GUIDE.md`, `docs/transport/DEVELOPMENT.md`, `data/vehicle_rates.json`,
`data/example_market_prices.csv`, backend test assertions, or the output of `python demo.py`. The
corpus figures (17,742 rows, 2,821 groups, 73.1%) describe the committed data as of 2026-09-17.
Do not replace them with the output of `mandi_pull.py analyse` on a working tree that holds later
untracked snapshots.
