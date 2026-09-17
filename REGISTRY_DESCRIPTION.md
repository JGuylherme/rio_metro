# Registry update — Rio Metropolitan 2.2.0

## Short description

Build Greater Rio's rail network from the Baixada Fluminense to Niterói and São
Gonçalo. Connect census-based neighborhoods, employment centers, airports,
universities, hospitals, beaches, shopping centers and major stadiums.

## Technical description / methodology

Population remains based on the 2022 Census, with 11,491,836 residents in the map
and no projection of total population to 2026. Census-sector age structure and
municipal employed-resident estimates determine spatial worker weights, calibrated
to PNAD Contínua 2026Q2 aggregate occupation rates. CNEFE 2022 dwelling addresses
improve residential placement; OSM and Overture mainly provide geometry and
complementary building use.

Formal destination geography comes from RAIS 2024 active employment relationships
by registered CEP, municipality and CNAE, allocated to compatible CNEFE establishment
addresses with footprint/floor-area support. This is an aggregate postal/activity
match, not an identified establishment-to-building linkage. Approximately 85.3%
of formal links have postal support; the rest require municipal fallback. CEMPRE
2024 remains a separate aggregate comparison. RAIS links and CEMPRE/PNAD people
are different statistical units and are not added as interchangeable counts.

PNAD metropolitan microdata supply informal broad activity proportions; finer
activity splits and locations remain explicit proxies. The published informality
control is 37.8%. Domestic and construction activity uses residential support;
other informal activity uses compatible establishment addresses.

Municipal commuting is constrained by Census 2022 local/other-workplace categories.
The public 2022 person microdata do not expose the municipality keys needed for a
current pairwise matrix. Other-municipality destination structure therefore uses
an explicitly historical Census 2010 sample-expanded OD prior, reconciled to current
modeled margins. This is not an observed 2022 pair matrix or an enumerated census
matrix. Home workers, foreign/multiple workplaces and estimated out-of-map
destinations are separately accounted for; inbound external workers are omitted.

Municipal origin–destination quotas are balanced first. Road-time gravity then
selects workplaces within those quotas. Directed OSM road paths and explicit access
connectors determine driving distances/times; both OD and workplace totals remain
exact after integer rounding. Road times do not include congestion or observed
transit journeys. Large workplace points aggregate multiple addresses.

The release adds a separate, sourced passenger/visitor/student layer, with all
conversion assumptions in special_demand_sites.json. These extra trip equivalents
are not additional census residents or employees. Beaches use municipal tourism
estimates; malls use operator footfall; stadium counts are smoothed annual activity,
with Nilton Santos limited to its documented 2024 Libertadores subset.

## Tags

`airports`, `entertainment`, `ferries`, `hospitals`, `parks`, `schools`, `universities`.
Beaches and malls fall under `entertainment`; no new tag names are introduced.

## Re-review note

The previous reviewed score is approximately 0.33 / Low. Request re-review using
`data-quality.proposed.json`, `QUALITY_REVIEW.md` and the validation tables. The
conservative filed workplace grain remains ADM3; the dossier requests assessment
of intermediate ADM4 from observed CEP/activity magnitudes. Conditional scenarios
span Medium to High; no reviewed grade is assigned by this repository.

## Release assets

Upload `dist/RIO.zip` and the separate `dist/manifest.json` to release `v2.2.0`.
The compatibility range is `>=1.7.0 <1.7.2`, including game 1.7.1. This repository
has not published these assets or changed the live Registry entry automatically.
