# MandiWise IEEE report

`mandiwise.tex` is the implementation report: IEEEtran conference format, two columns. It runs to
five pages, references included. Every chart is drawn with pgfplots from the CSV files in `data/`;
the only images are the UI screenshots in `figures/`.

## Build

**Overleaf:** upload the whole `report/` folder, including `data/` and `figures/`. Set the compiler
to **pdfLaTeX** (Menu → Compiler).

**Locally:** `tectonic mandiwise.tex`, or run `pdflatex mandiwise.tex` twice.

The bibliography is inline, so no BibTeX run is needed. Packages: IEEEtran, cite, amsmath,
graphicx, booktabs, array, url, xcolor, tikz, pgfplots (with fillbetween), pgfplotstable and
enumitem. All of them ship with TeX Live and Overleaf.

## Chart data: regenerate, never edit

```bash
python research/report_figures.py      # from the repo root
```

The script reads only **git-tracked** files under `data/`, so an uncommitted local pull can never
change a published figure. Before writing anything it asserts that it reproduces
`research/findings.md`: 2,821 groups, a 73.1% median, and 45 liquidity pairs with a median of 21.
It prints every number the captions quote, and two runs produce identical CSVs.

| CSV | Figure |
|---|---|
| `potato_band.csv` | Fig. 3: weekly cheapest vs dearest Patiala mandi for potato |
| `dispersion_hist.csv`, `dispersion_by_crop.csv` | Fig. 4: distribution of dispersion, and dispersion by crop |
| `liquidity.csv` | Fig. 5: reporting days per mandi × crop |
| `cost_per_quintal.csv` | Fig. 6: the canonical engine on the placeholder rate card, at 60 km |

Fig. 8 plots the measured benchmark from `research/engine_benchmark.md`. The 12-class enumeration
point is labelled as an extrapolation.

## Figures

| File | Figure | How it was made |
|---|---|---|
| `figures/fig_ranking.png`, `figures/fig_ranking_mobile.png` | Fig. 7 | Chrome, driven by a script against the live ranking API from PR #4 on a scratch database, 2026-11-19. Desktop 1440 px wide; mobile at a true 390 px viewport. |
| `figures/ceda_logo.png` | Figs. 3–5 | **Still needed.** CEDA requires its logo on visuals derived from its data (`docs/DECISIONS.md`, 2026-09-04). The `\cedalogo` slot shows it once the file exists; the attribution text is already in every caption. |

`fig_react_markets.png` and `fig_react_transport.png` are kept for the presentation but are not
used in the report.

## Test counts

The macros at the top of `mandiwise.tex` hold the counts measured on 2026-11-19:
- backend: 78 passed, 1 skipped;
- root: 5;
- frontend: 7, on PR #4.

Re-measure if anything else merges first.
