## Re-review request: Rio Metropolitan 2.2.0

Please re-review `rio-metropolitan` after the data-pipeline changes in v2.2.0.
The previous review in #10682 / #10680 was approximately 0.33 / Low.

The implementation now uses RAIS 2024 CEP/activity headcounts and CNEFE 2022
establishment/dwelling addresses throughout the covered municipalities. Census
age structure and municipal employment feed PNAD controls. Informal activity
proportions come from weighted PNAD microdata rather than the old 75/25 spatial blend.

Municipal OD is fixed before road-time workplace disaggregation. Census 2022 local
containment is enforced; other-municipality destinations use a clearly labeled
historical Census 2010 sampled prior. I am not claiming an observed 2022 pair matrix
or enumerated OD. Both municipal pairs and modeled workplace capacities close
exactly after integer rounding.

Please assess the effective workplace grain: 85.3% of formal links have CEP support,
14.7% need municipal fallback, and 9.7% of all links have postal address extents over
5 km. The proposed JSON conservatively retains ADM3; the dossier presents the
case and limitations for an intermediate ADM4 classification. CNEFE addresses are
not an authoritative building cadastre or a shared-ID match to RAIS establishments.

For residents, the request concerns measured age-15–59 census-sector magnitudes
preserved through aggregation, not measured employed people per building. Please
also review the appropriate placement/intensity classification: the form lacks an
exact option for this CNEFE/OSM/Overture hybrid with local statistical calibration.

Evidence, reproducible code, source hashes, municipal/OD CSVs, outlier warnings and
conditional scoring are linked in the v2.2.0 methodology and quality dossier.
The local scenarios are approximately 0.51–0.64, not an awarded tier. I welcome
correction of any classification that the evidence does not support.

Special demand, beaches, malls, stadiums and water rendering are gameplay changes
and are not included in the data-quality score argument.
