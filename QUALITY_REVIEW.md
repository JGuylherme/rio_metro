# Data Quality — re-review dossier, version 2.2.0

**Previous reviewed tier: Low, approximately 0.33. No new tier is assigned locally.**
The implementation and evidence are in [METHODOLOGY.md](METHODOLOGY.md) and
[reports/quality](reports/quality). Special demand and smoother water do not raise
this score.

## Before and after

| Registry criterion | Previously reviewed | Implemented change / qualification |
| --- | --- | --- |
| Workplace count | Registered CEMPRE / RAIS | RAIS 2024 active links remain registered, not physical-workplace enumeration |
| Workplace magnitude grain | ADM3 across the metro; Rio-only bairro detail | Observed CEP × CNAE counts across all covered municipalities; 85.3% postal match, 14.7% municipal fallback; request assessment of effective ADM3–ADM4 grain |
| Workplace resolution | OSM / Overture footprints | CNEFE non-residential address units plus complementary footprints; no authoritative building-cadastre claim |
| Workplace intensity | Generic activity assumptions | Postal/activity totals calibrate 19 activity classes; unknown address classes and informal destinations still modeled |
| Resident count | Total population × aggregate rates | Measured Census age-15–59 structure, municipal employed-resident calibration, PNAD stratum controls; request working-age, not fine-scale employed enumeration |
| Resident magnitude grain | Census sectors | Same measured sectors and exact source totals retained; output aggregates nearby units |
| Resident placement | Footprint-area assumptions | CNEFE dwelling-unit anchors support 99.23% of population; missing addresses retain old anchors; not measured people per building |
| OD | Synthetic global gravity, score zero | Enforced Census 2022 local containment plus historical 2010 sampled destination structure; balanced municipal OD before fine road-time gravity |
| OD grain | None | Municipal; no observed 2022 pair matrix or full-enumeration claim |
| Point placement detail | Thousands of demand points | 8,650 source points; density is a performance choice, not a quality multiplier |

The exact CEP spans and fallback proportions are in
[postal_grain_summary.json](reports/quality/postal_grain_summary.json) and
[postal_grain_diagnostics.csv](reports/quality/postal_grain_diagnostics.csv).
About 9.7% of all formal links match postal support whose address extent exceeds
5 km. A fine coordinate does not remove that magnitude uncertainty.

## Conditional scoring

The current [official rubric](https://github.com/Subway-Builder-Modded/registry/blob/main/docs/data-quality.md)
uses `W/R = (0.5 count + 0.5 resolution × intensity) × grain` and
`composite = 0.50 W + 0.35 R + 0.15 OD`. High starts at 0.60.

[quality_score.py](quality_score.py) reproduces these **classification scenarios**:

| Scenario | W | R | OD | Composite | Conditional tier |
| --- | ---: | ---: | ---: | ---: | --- |
| Municipal workplace, conservative residential placement, OD discounted | .453 | .665 | .350 | **.512** | Medium |
| Municipal workplace, measured census-unit residence, sampled historical OD accepted | .453 | .760 | .525 | **.571** | Medium |
| Submunicipal workplace accepted, measured census-unit residence, OD discounted | .583 | .760 | .350 | **.610** | High |
| Submunicipal workplace and sampled historical OD accepted | .583 | .760 | .525 | **.636** | High |

These scenarios assume the locally calibrated fine-type intensity rung is accepted.
The .512–.636 interval is not a confidence interval or guaranteed floor. Reviewers
may score unclassified establishments, informal allocation, residential proxies or
historical OD more conservatively. The 2022 observations constrain local retention;
other destination shares remain a reweighted **2010** survey prior. Historical
sampled pairs must never be described as enumerated or observed in 2022.

The conservative interpretation remains **Medium**. High is plausible only if the
review accepts the effective submunicipal workplace grain and the residence/OD
classifications. More address points alone do not resolve the remaining limits.

## What still limits High

- Anonymous RAIS cannot be linked to individual CNEFE establishments by a shared ID.
- Municipal fallbacks and large/general CEPs weaken fine workplace magnitude.
- CNEFE activity recognition is partial; footprints and heights supply generic
  within-class capacity, even though class totals are locally fitted.
- Informal workplace locations are proxies; PNAD measures aggregate activity shares.
- The public 2022 person microdata do not expose municipality keys required for
  the requested current pairwise matrix. Updated observed municipal pairs would be
  the strongest next OD improvement.
- The game model omits external inbound commuters and excludes estimated outbound
  workers. Current jobs are reconciled to containment in a closed map; raw RAIS
  links are retained separately and not presented as interchangeable workers.
- Very large destination points are multi-address aggregations. Their modeled
  capacities are preserved, but they are not verified individual-building capacities.

## Reference comparisons

Reviewed [Tallinn answers](https://github.com/Subway-Builder-Modded/registry/blob/main/maps/yukina-ee-tallinn/data-quality.json)
use registered municipal workplace counts, an authoritative building layer,
calibrated type weights, employed-resident data and structured OD constraints.
[Vilnius answers](https://github.com/Subway-Builder-Modded/registry/blob/main/maps/yukina-lt-vilnius/data-quality.json)
illustrate the distinction between measured workplace/resident margins and merely
balancing modeled totals. Rio does not inherit their classifications automatically.

All proposed answers remain **self-reported**, with `reviewed_by: null`. A Registry
maintainer must confirm the classification. Neither the quality floor nor a change
to the legacy `source_quality` field awards an upgrade.
