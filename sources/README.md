# Frozen official Census 2022 inputs

All files contain aggregate statistics, not individual records. [provenance.json](provenance.json) records source URLs, retrieval date, transformations and SHA-256 hashes.

- `census_workers_2022.json`: SIDRA 10261, variable 4090, municipal employed people aged 14+, all sex/race/employment-position categories set to Total. RJ has 92 municipalities.
- `census_workers_metadata.json`: official variable and category definitions.
- `census_commuting_2022.json`: SIDRA 10329, variable 13373; workplace-location categories, other dimensions set to Total. Used only for the independent containment diagnostic, not for enforced O/D.
- `census_commuting_metadata.json`: official definitions, including the different population universe of Table 10329.
- `census_demography_rj_2022.csv`: 40,519 RJ records filtered from the official national demographic CSV. Count each `CD_setor` once.

The [official variable dictionary](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/dicionario_de_dados_agregados_por_setores_censitarios_20260520.xlsx) defines `V01034`–`V01039` as population aged 15–19, 20–24, 25–29, 30–39, 40–49 and 50–59, respectively. Their sum is the complete measured **15–59** band. It is not 15–64 or employed residents by sector. `V01006` is all-age population.

`X`/missing demographic breakdowns are not zero. Their age counts use a documented municipal fallback, audited by represented population. A SIDRA `-` denotes numeric zero. Geometry/total-population fallbacks use deduplicated Census 2022 tract attributes.

Statistics are held at their published granularity. The source files do not contain neighborhood employment observations outside Rio or a complete home-to-work municipality matrix.
