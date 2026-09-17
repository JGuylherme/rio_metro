# Pipeline audit — before the 2.2 data upgrade

## Existing chain

`build_rio.py` downloads/caches geography, runs `census_demand.generate`, configures the map, renders tiles, previews and packages. `--employment-only` reuses geography. `package_rio.py` exports workers and adds the separately audited non-work layer.

| Stage | Existing implementation | Limitation / decision |
| --- | --- | --- |
| Population | `census_demand.py`: deduplicated Census 2022 sectors, boundary coverage, one sector anchor, 800 m performance aggregation within neighborhood | Preserve counts and lineage; refine anchor using observed CNEFE dwelling addresses |
| Buildings | `geography.py`, `prepare_rio.py`, `fetch_overture.py`: OSM + Overture geometry, uses and heights | Preserve geometry/tiles; geometry is not a population or worker count |
| Resident workers | `census_workers.py`: measured age 15–59 per sector, calibrated to Census municipal employment | Already better than three PNAD all-age rates; retain demographic structure, explicitly reconcile PNAD control |
| Formal jobs | `employment.py`: CEMPRE municipal weights; RAIS 2023 neighborhood shares in Rio only | Replace generic within-area weights with RAIS activity controls + CNEFE establishment locations; raw anonymous RAIS is not address-level employment |
| Informality | PNAD metropolitan informality, 75% residence / 25% formal placement | Replace with documented activity-compatible geography where supported; do not claim observed informal workplaces |
| Pairing | Global gravity, iterative origin/neighborhood balancing, then independent origin rounding | Import strongest available official commute constraints; municipality-first balancing; expose target adjustments and rounding |
| Roads | OSM directed shortest paths; special demand router preserves edge lengths and access connectors | Reuse shared router and cache; invalidate caches when points/graph change |
| Special demand | 27 destinations, seven tags, modeled conversion of cited attendance/bed/enrollment counts | Extend separately; does not improve commute rubric |
| Release | 8 data assets in ZIP, separate compatibility manifest, native point/pop schema | Preserve schema and compatibility; rebuild demand only |

## Source boundaries to verify before claiming improvements

- Anonymous RAIS municipality/CNAE/size/headcount does not permit a deterministic match to a named CNEFE address without a shared identifier.
- CNEFE coordinates locate address units; they do not measure employees or establish an authoritative building footprint cadastre.
- Censo 2022 commute questions are from the sample questionnaire. Expanded survey OD cannot claim the rubric's full-enumeration matrix rung.
- The currently cached SIDRA 10329 table describes local/other-municipality/foreign/multiple locations; it does not name each destination municipality. Do not manufacture observed pairs from it.
- Census, PNAD, CEMPRE and RAIS have different years and universes. Any reconciliation must retain original counts and publish factors.
- Keep the published reviewer decision as historical. Proposed answers must be self-reported and must not carry a forged reviewer stamp.

No geography/tiles need rebuilding for this upgrade. Existing worker demand and metadata are checkpointed before transformation. Large sources stay in the ignored `data/` cache; URLs, hashes, configuration, scripts and aggregate evidence remain reproducible.
