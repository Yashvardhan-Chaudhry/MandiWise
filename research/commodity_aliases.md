# Commodity name aliases — data.gov.in ↔ CEDA

Seed for the `commodity_alias` table in `docs/ARCHITECTURE.md` §5, which the ingestion pipeline's normalise step (§4, step 3) depends on. That step is called out there as *"the single most underestimated part of this pipeline"* — this file is the first evidence of why.

**Sources compared**
- `data.gov.in` AGMARKNET live feed — 57 distinct commodity names, from the Punjab pulls of **2026-09-04** and **2026-09-07** (`data/punjab_*.json`). Two days of one state only, so this list is a floor, not the full vocabulary.
- CEDA Agri Market Data — 453 commodity names, fetched **2026-09-07** from `/api/commodities`.

**Nothing here is guessed.** Rows are graded by how they were established, and the unresolved ones are left unresolved rather than filled in with a plausible-looking id.

---

## Summary

| Category | Count |
|---|---|
| Names identical in both sources | 40 |
| Differ only by punctuation/spacing | 10 |
| Spelling variants — proposed, need confirmation | 5 |
| Ambiguous or unmatched — need a human decision | 2 |
| **Total distinct data.gov.in names seen** | **57** |

Roughly **30% of names do not match exactly** across two sources describing the same markets. Any join on raw commodity strings would silently drop those rows.

---

## Verified by use

These ids returned real Patiala data in the CEDA backfill, so the mapping is confirmed end to end rather than by name similarity alone.

| data.gov.in | CEDA | id | Status as of 2026-09-07 |
|---|---|---|---|
| Potato | Potato | 24 | ✅ confirmed — 2,657 rows / 741 days |
| Onion | Onion | 23 | ✅ confirmed — 2,680 rows / 710 days |
| Tomato | Tomato | 78 | ✅ confirmed — 2,693 rows / 742 days |
| Green Chilli | Green Chilli | 87 | ⏳ backfill in progress |
| Brinjal | Brinjal | 35 | ⏳ queued |
| Cauliflower | Cauliflower | 34 | ⏳ queued |
| Bhindi(Ladies Finger) | Bhindi (Ladies Finger) | 85 | ⏳ queued |
| Cucumbar(Kheera) | Cucumber (Kheera) | 159 | ⏳ queued |

The queued rows are name matches that have been *requested* but have not yet returned data — update the status column as the backfill lands, and treat them as unconfirmed until then.

## Differ only by punctuation or spacing

Normalising case, spaces and punctuation makes these identical. High confidence, but only the two above (85, 159) are confirmed by a successful data pull.

| data.gov.in | CEDA | id |
|---|---|---|
| Bhindi(Ladies Finger) | Bhindi (Ladies Finger) | 85 |
| Coriander(Leaves) | Coriander (Leaves) | 43 |
| Cucumbar(Kheera) — *see also spelling variants* | Cucumber (Kheera) | 159 |
| Cowpea(Veg) | Cowpea (Veg) | 89 |
| French Beans(Frasbean) | French Beans (Frasbean) | 298 |
| Ginger(Dry) | Ginger (Dry) | 27 |
| Ginger(Green) | Ginger (Green) | 103 |
| Mint(Pudina) | Mint (Pudina) | 360 |
| Mousambi(Sweet Lime) | Mousambi (Sweet Lime) | 77 |
| Pear(Marasebu) | Pear (Marasebu) | 330 |
| Squash(Chappal Kadoo) | Squash (Chappal Kadoo) | 332 |

## Spelling variants — proposed, not yet confirmed

Punctuation normalisation is not enough here; the words themselves are spelled differently. Each looks unambiguous, but **confirm before relying on it** — a wrong id silently attributes one crop's prices to another.

| data.gov.in | Proposed CEDA | id | Note |
|---|---|---|---|
| Cucumbar(Kheera) | Cucumber (Kheera) | 159 | "Cucumbar" vs "Cucumber" — requested in the backfill, not yet returned |
| Raddish | Radish | 161 | doubled "d" |
| Mashrooms | Mushrooms | 340 | "Mash" vs "Mush" |
| Chilly Capsicum | Chilli Capsicum | 88 | "Chilly" vs "Chilli"; note CEDA also has plain `Capsicum` (164), which the feed lists separately too |
| Ridgeguard(Tori) | Ridge gourd (Tori) | 160 | "ridgeguard" vs "ridge gourd" — the feed's spelling is not a real word |

## Unresolved — needs a human decision

| data.gov.in | Problem |
|---|---|
| `Elephant Yam(Suran)/Amorphophallus` | CEDA has **two** plausible targets: `Elephant Yam (Suran)` (296) and `Amphophalus` (102). These look like duplicate entries for the same crop on CEDA's side. Picking one arbitrarily risks splitting or merging series wrongly — someone needs to check whether both carry data. |
| `Pea Pod/Pea Cod/हरी मटर` | No candidate above threshold. The name carries **three** labels including Devanagari. The feed already lists `Peas Wet` separately, so this may or may not be the same thing. Do not map without checking. |

---

## Practical notes for the pipeline

1. **Names are not stable identifiers.** Map to canonical ids at ingestion; never join on the raw string.
2. **The feed contains mixed-script names.** `Pea Pod/Pea Cod/हरी मटर` is real data from the live API. Handle text as UTF-8 everywhere — writing this list with Windows' default `cp1252` console encoding raised `UnicodeEncodeError` on exactly that row, which is the kind of thing that takes down a nightly ingestion job.
3. **One source's vocabulary is finer than the other's.** CEDA carries 453 commodities against 57 seen in two days of one state, so a data.gov.in name may match several CEDA entries (see `Chilly Capsicum` / `Capsicum`).
4. **This list will grow.** It covers two days of Punjab only. Other states and seasons will introduce names not seen here; the alias table needs to be additive, with unmapped names surfaced rather than silently dropped.

## Attribution

CEDA names and ids from: *CEDA Agri Market Data (CEDA-AMD), 2000-2023. Centre for Economic Data & Analysis, Ashoka University* — free for non-commercial use, see `docs/DECISIONS.md`.
