# Rio Metropolitan — methodology 2.2.0

This version preserves the Census population, sector lineage, buildings, terrain,
water and binary collision data. It replaces employment placement and commuting.
It does not claim an observed 2022 municipality-to-municipality matrix.

## Sources and statistical units

| Component | Source / vintage | Observed unit | Use |
| --- | --- | --- | --- |
| Population | IBGE Census 2022, final sector geography | Census sector, all ages | Fixed population; no projection to 2026 |
| Age structure | Census 2022 demographic aggregates, V01034–V01039 | Residents aged 15–59 per sector | Fine spatial worker weights |
| Employed residents | Census 2022, SIDRA 10261 | Sample-expanded employed people aged 14+ per municipality | Municipal employment differences |
| Addresses | [CNEFE 2022 GeoJSON, release 20240910](https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/GeoJSON/) | Address units and species | Dwelling and establishment anchors |
| Formal jobs | [RAIS 2024 establishment microdata](https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/microdados-rais-e-caged), second processing | Active employment relationships, CNAE, size band, registered CEP and municipality | Main employment geography |
| Employment comparison | [CEMPRE 2024, SIDRA 9509](https://sidra.ibge.gov.br/tabela/9509) | Employed personnel per municipality | Independent comparison, not added to RAIS |
| Occupation / informality | PNAD Contínua 2026Q2, SIDRA 4093/5918 and quarterly microdata | Capital/metropolitan/state controls; weighted broad activity groups | Current rates on fixed 2022 population; informal composition |
| Current commute constraints | [Census 2022, SIDRA 10329](https://sidra.ibge.gov.br/tabela/10329) | Home / own municipality / another municipality / foreign / multiple places | Enforced local containment and commuter universe |
| Historical destination structure | [Census 2010 RJ sample](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/) | Expanded residence–work municipality pairs | Explicitly historical prior for other-municipality destinations |
| Buildings | Existing OpenStreetMap / Overture snapshots | Footprints, use and height | Complementary geometry and floor-area proxy |
| Roads | Existing OSM directed graph | Arc lengths, travel times and direction | Shortest road-time paths; no external routing requests |
| Depth | Existing GMRT raster | Raster bathymetry | Collision depth; smoothed vector bands for rendering |

Download URLs, file sizes and SHA-256 hashes are in `sources/quality_downloads_*.json`.
The older census snapshot is documented in [sources/README.md](sources/README.md).
The public 2022 microdata were inspected against their September 2026 layout:
the public person file exposes state and work-location categories, but not the
municipal origin/destination identifiers needed to construct the requested matrix.
Controlled-access documentation is not evidence that those fields are public.

## Residents and employed people

Each original sector contributes its unchanged count to the same residential
aggregation. Nearby CNEFE dwelling units (species 1; coordinate quality 1–3) select
an actual dwelling anchor near the dwelling-weighted center. Levels 4–6 are too
coarse and excluded. Quality 3 coordinates are estimated. Water candidates are
excluded. Missing usable addresses retain the previous anchor and are reported.
This is not an authoritative building cadastre or per-building person count.

The complete measured age bins 15–59 supply spatial weights. Municipal Census
employed totals calibrate those weights. Suppressed age cells use a municipal
age-share proxy, affecting 0.697% of represented population. Partial municipalities
use their represented age share as an employment-coverage proxy.

PNAD then calibrates capital, metropolitan remainder and other-area strata using
occupied/all-age-population ratios. It preserves the relative age and municipal
employment pattern; it does not apply one flat worker rate to every point. The
population stays at **11,491,836**; the calibrated employed estimate is **5,519,167**.
Age, employed, non-employed and travel-producing populations are separate reports.
People older than 59 with jobs are represented through municipal calibration, not
located individually by the age proxy. Fine-scale workers remain estimates.

## Formal employment locations

The anonymous RAIS establishment release has CEP, municipality, detailed CNAE,
size band and active links, but no shared business identifier permitting an exact
RAIS–CNEFE establishment match. We aggregate links by municipality, CEP and activity.
The 26 covered municipalities contain **3,616,925 active links** in this input.
RAIS is a registered-address anchor, not verified physical workplaces.

CNEFE non-residential species provide candidate addresses. Names and species are
classified into 19 activity classes; no personal names are exported. OSM/Overture
use complements unclassified records. Nearby footprints within 75 m supply a
floor-area proxy, with height/3 clamped to 1–40 floors. Shared footprints divide
their mass among attached addresses. These geometry assumptions are not measured
employee capacity.

Allocation follows: same CEP and activity; same CEP unclassified establishments;
same municipality and activity; municipal unclassified establishments; finally
all establishments in that municipality. Every fallback is recorded. Water units
are excluded. Formal job mass is allocated to non-residential address units;
mixed residential buildings can contain real CNEFE businesses and remain flagged
as ambiguous rather than being treated as proven office buildings.

The total for each RAIS postal/activity group calibrates its proxy density. About
85.3% of formal links match postal support; 14.7% use municipal fallback. Exact
postcode spans and unusually broad areas are reported separately. CEP precision
does not establish measured worker counts at an individual building.

## Informality and compatible totals

Weighted PNAD metropolitan microdata classify informal main jobs using VD4009
categories 2, 4 and 10, or categories 8/9 without CNPJ (V4019=2), with V1028 weights.
The result is 37.826%, consistent with the published 37.8% aggregate used by the
model. Informal broad activity shares are observed survey estimates. Splits within
broad groups use RAIS activity composition as an explicit proxy.

Informal activity is placed at compatible CNEFE business units; domestic work and
construction use residential anchors. Those locations are modeled, not an inventory
of informal establishments. RAIS relationships and PNAD people have different
universes: formal and informal geography become normalized weights, not raw counts
added together. The initial spatial blend is 62.2% formal / 37.8% informal.
Subsequent commute constraints can change municipal destination proportions.

## Hierarchical commuting

1. Census 2022 Table 10329 defines local work outside home and other-municipality
   shares. Its sample universe differs from the age-14+ employment table; applying
   those shares is documented as a proxy, not exact population identity.
2. Home workers, foreign/multiple workplaces and estimated destinations outside
   the map are excluded from recurring single-workplace trips. This does not
   remove them from census population or the employed report.
3. Historical 2010 expanded pairs (V0010 weights, V0660=2/3, V6604 destination)
   inform the other-municipality shares. A 0.1% job-weight smoothing prior permits
   pairs absent in the old sample. It is modeled support, not a new observation.
4. Partially covered destinations use the fraction of placed formal RAIS mass
   inside the map as a coverage proxy, including for informal destinations. External
   destinations are reported but not exported; incoming workers from outside the
   map are not represented. This is a closed playable system.
5. Local diagonal targets stay fixed. Infeasible initial destination targets are
   projected to the bounds required by that containment. Both the initial scaled
   weights and reconciled targets are retained. Raw official source counts do not
   change. The reconciliation reflects incompatible vintages/universes.
6. IPF balances intermunicipal flows to the modeled origin and destination margins.
   Integral residual-network rounding preserves both margins exactly.
7. Each fixed municipal pair is shared among residential anchors. Only then does
   road-time gravity choose the specific workplace. Sparse routing support includes
   nearby workplaces and large centers, expanding when necessary for feasibility.
   No independent sampling can change a municipal quota.

Workplace points aggregate actual addresses in 1.5 km cells for performance. A
formal-job cluster chooses a representative business address, never a residential
proxy when formal candidates exist. **The cell size is an output choice, not a
claim of observed 1.5 km employment data.** Each point's modeled capacity is fixed
before fine flow fitting and preserved after integer rounding.

Road routing uses shortest directed travel-time paths on the largest strongly
connected road component. Actual lengths are summed along those paths. Access
connectors use 20 km/h and are included explicitly; connectors over 1.5 km and trips
over two hours are warnings. This road-only model omits ferry travel, transit,
congestion, weekly attendance and telework frequency. Route caches key the graph,
ordered coordinates and routing implementation. No millions of web requests occur.

## What validation establishes

`reports/quality/` contains municipal population/worker/job accounts, exact OD
target errors, comparison to the historical reference, travel histograms, actual
point capacities, address placement, postal extent/fallbacks and centralities.
MAE/RMSE against balanced targets test implementation. Differences from 2010 measure
change from the historical prior; neither is an independent validation of 2022
pairwise flows. There are no fabricated `observed_2022_pair` values.

`quality_validation.py` checks endpoints, memberships, integer counts, population
preservation, both municipal margins, each OD pair and geometry. `validate_rio.py`
additionally checks collision data, all tile protobufs, sampled decoded geometry,
special trips and the complete release ZIP. In-game behavior remains a manual test.

## Gameplay layer and provenance

See [SPECIAL_DEMAND.md](SPECIAL_DEMAND.md). Extra passenger, visitor and student
trip equivalents are exported separately from employment. They are not unique
inhabitants, employee counts or evidence for a higher commuting-data tier.
Only AIR_/UNI_ have native category behavior identified in the game; other
categories use ordinary supported demand groups. Registry tags describe the content.

See [QUALITY_REVIEW.md](QUALITY_REVIEW.md) for conditional scoring and remaining
limits. No code stamps a reviewed tier or impersonates a maintainer.
