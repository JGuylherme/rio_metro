## Rio Metropolitan 2.2.0

- RAIS 2024 postal/activity employment and CNEFE 2022 residential/workplace addresses.
- Census age structure and municipal employment calibrated to PNAD; informal activity shares from PNAD microdata.
- Hierarchical municipal OD: Census 2022 local containment with an explicitly historical 2010 sampled destination prior, followed by road-time gravity.
- Exact municipal-pair and modeled workplace totals after integer rounding; 8,650 source points.
- 38 special destinations: airports, universities, hospitals, ferry access, schools, parks, Copacabana/Ipanema/Leblon and neighboring beaches, malls, Maracanã and Nilton Santos.
- Smoother vector ocean rendering with unchanged collision depths.
- Compatibility manifest includes Subway Builder 1.7.1.

Census population: **11,491,836**. Exported work commuters: **4,414,637**.
Additional non-work trip equivalents: **314,835**. Total release demand: **4,729,472**.
These demand units are not unique inhabitants.

Validation: 21 automated tests; 676 municipal OD pairs and modeled capacities exact;
all 26,188 map tiles checked at protobuf/property level, sampled full geometry;
complete ZIP integrity and demand accounting passed. No in-game simulation test is claimed.

Data Quality re-review is requested separately. The existing reviewed tier remains
in force until a maintainer confirms new answers. No observed 2022 pairwise OD or
verified per-building employee counts are claimed. See METHODOLOGY.md,
QUALITY_REVIEW.md and reports/quality for assumptions, source years and limitations.
