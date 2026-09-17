# Employment and commuting — version 2.2.0

The current methodology is [METHODOLOGY.md](METHODOLOGY.md).

- Census population remains **11,491,836**.
- Census age structure and municipal employment, calibrated to PNAD 2026Q2,
  produce **5,519,167 employed residents**.
- Home-working, foreign/multiple workplaces and estimated out-of-map destinations
  are accounted for separately. **4,414,637 commuters** enter the playable work model.
- **RAIS 2024**, CEP/activity and **CNEFE 2022** now determine formal workplace
  geography throughout the map. CEMPRE is a separate comparison.
- PNAD microdata supply informal activity proportions; within-group and spatial
  allocation assumptions are explicit. The old 75% homes / 25% formal blend is gone.
- **Census 2022 local containment is enforced.** Other-municipality destinations use
  an explicitly historical **2010 sampled OD prior**, not an observed 2022 matrix.
- Municipal OD, origins and workplace capacities balance exactly after integer
  rounding. Road-time gravity only disaggregates the fixed municipal quotas.

## Outputs

See [reports/quality](reports/quality) for resident/commuter separation, municipal
accounts, postal matching, activity calibration, source-versus-modeled quantities,
OD comparisons, route warnings, travel histograms and centralities.

`employment_by_municipality.csv` and `employment_by_neighborhood.csv` summarize the
new model. `commuting_comparison.csv` contains current municipal pairs, target error
and historical change; its schema replaces the old diagnostic-only share report.
`resident_workers_by_municipality.csv` retains the **intermediate Census 2022**
calibration. Final PNAD employment and exported commuters are reported separately
under `reports/quality/`; do not confuse the intermediate count with the release.

The source `build/RIO/demand_data.json` keeps full census residents. Packaging
exports balanced work trips and adds [special trips](SPECIAL_DEMAND.md). Extra
trip equivalents are not new employees or inhabitants.

The previous CEMPRE/RAIS-2023 pipeline remains in `employment.py` as historical code.
The build's employment/quality modes now invoke `quality_pipeline.py`. Only
[the maintainer's re-review](QUALITY_REVIEW.md) can award a new Registry tier.
