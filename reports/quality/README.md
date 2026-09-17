# Quality evidence — 2.2.0

Start with [municipal_validation.csv](municipal_validation.csv),
[od_comparison.csv](od_comparison.csv), [warnings.json](warnings.json), and
[score_scenarios.json](score_scenarios.json).

| Files | Interpretation |
| --- | --- |
| `summary.json`, `reproducibility.json` | Build totals, method/configuration, source and code hashes |
| `municipal_validation.csv` | Fixed census population; employed vs commuters; raw RAIS/CEMPRE and modeled jobs; inbound/outbound counts and leading partners |
| `resident_age_structure.csv`, `resident_workers.csv`, `resident_commuters.csv` | Age weights, Census employment intermediate, PNAD employed/non-employed, exported commuters |
| `pnad_resident_controls.csv`, `pnad_microdata_audit.json`, `informal_activity.csv` | Aggregate calibration and weighted informal activity shares, with fine-split proxies |
| `residential_placement.csv` | CNEFE dwelling matching, fallback and old/new coordinates |
| `rais_postal_calibration.csv`, `postal_grain_diagnostics.csv`, `postal_grain_summary.json` | Raw link totals, candidate support, fitted density, CEP extents and municipal fallback |
| `workplace_placement.csv`, `workplace_capacities.csv` | Multi-address aggregation, formal/informal weights, fixed vs realized point capacities |
| `commuter_universe.csv` | Exclusions, containment, boundary coverage, initial vs reconciled job targets |
| `od_municipal_targets.csv`, `od_actual.csv`, `od_comparison.csv`, `od_metrics.json` | Historical observations vs modeled seeds, fixed targets and realized pairs |
| `travel_distribution.csv`, `travel_time_census_comparison.csv` | Model histograms; independent comparison with Census automobile-duration bins |
| `road_access.csv`, `routing_support.csv` | Connector length and sparse support expansion |
| `centralities.csv`, `point_distribution.csv` | Model counts, density and jobs/residents ratios; bairro classification follows representative point location |
| `workplace_water_exclusions.csv`, `warnings.json` | Invalid candidate exclusions and outlier diagnostics |

## Reading differences correctly

Zero OD target errors prove the balancing implementation preserves its constraints;
they do not prove a perfect match to real 2022 flows. `observed_2022_pair` is blank
because no current public pairwise matrix was found. Comparison against 2010 is
historical change, not a present-day accuracy score.

RAIS employment relationships, CEMPRE personnel, PNAD employed people and the closed
map's commuters are different populations. Their quantities are shown separately;
only differences between equivalent model targets and realized values are called
errors. Partial-municipality census comparisons use the represented sector allocation,
not a demand that a clipped map contain the entire municipality.

The car-time comparison is independent, not used to tune gravity. It compares
surveyed automobile users returning at least three days/week in 2022 with road
times for all modeled commuters. Static OSM times exclude congestion and tend to
be much shorter. Mode, coverage and vintage also differ. These are material limits,
not evidence for a higher OD rung.

Workplace capacity means the model's assigned multi-address cluster total, not a
survey of each representative building. Large clusters can cross bairro boundaries;
centrality counts and densities classified by their representative location should
be read with that aggregation limitation, especially around the Centro.
