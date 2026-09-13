# Distribution of Workers and Jobs

The generation combines the 2022 resident population with 2026 employment rates and 2023–2024 job-location references. It preserves the map's original population: not all residents are projected to 2026.

## Sources Used

| Source                                                                                                                                    | Reference           | Use                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------- |
| [IBGE PNAD, Table 4093](https://sidra.ibge.gov.br/tabela/4093)                                                                            | 2nd quarter of 2026 | Employed population, employment level, unemployment, and informality |
| [IBGE PNAD, Table 5918](https://sidra.ibge.gov.br/tabela/5918)                                                                            | 2nd quarter of 2026 | Total population compatible with PNAD                                |
| [IBGE CEMPRE, Table 9509](https://sidra.ibge.gov.br/tabela/9509)                                                                          | 2024                | Total employed personnel in establishments in each municipality      |
| [RAIS neighborhood map, Portal da Geografia Econômica Carioca](https://www.arcgis.com/home/item.html?id=bed7ea7dfc424f988b7dcb4a6b5156ce) | 2023                | Neighborhood shares of formal employment in Rio                      |
| IBGE 2022 Census, final census tracts with attributes                                                                                     | 2022                | Residents, municipality identification, and study-area coverage      |

The downloaded files and their source addresses are stored in `data/employment_sources/`. The RAIS map contains 160 records, one of which is labeled “Não Identificado” (“Unidentified”), has no geometry, and contains 6,259 employment relationships; no invented coordinates are assigned to this record. The 159 neighborhoods with defined geometries determine the relative distribution of jobs that can be geographically located. Records labeled “Todos” (“All”) are not combined with activity categories, as doing so would duplicate jobs.

## Resident Workers

PNAD counts employed people by place of residence. For the quarter used:

| PNAD Area                                    |  Employed | Total Population | Employed / Total Population |
| -------------------------------------------- | --------: | ---------------: | --------------------------: |
| Municipality of Rio de Janeiro               | 3,353,000 |        6,737,000 |                      49.77% |
| Metropolitan Region                          | 6,018,000 |       12,534,000 |                      48.01% |
| Rest of the metropolitan area, by difference | 2,665,000 |        5,797,000 |                      45.97% |
| State of Rio de Janeiro                      | 8,262,000 |       17,252,000 |                      47.89% |

These rates are applied to residents within the study area, using rounding that preserves the total. The capital uses its own rate; the other metropolitan municipalities use the aggregate rate for the remainder of the metropolitan area; small portions outside the metropolitan area use the state rate. No current neighborhood-level employment rates are artificially inferred from PNAD.

The published metropolitan employment level of 56.8% uses the population **aged 14 or older** as its denominator. The unemployment rate of 7.7% uses the **labor force** as its denominator. Neither percentage should be applied directly to the 11.52 million residents of all ages.

## Job Destinations

1. CEMPRE provides municipal weights for the location of establishments. For municipalities only partially covered by the map, the population share within the study area is used as an approximation of the share of jobs covered. This is a limitation, particularly in municipalities with industrial hubs located far from residential areas.

2. Within Rio de Janeiro, the weights are distributed according to RAIS employment relationships by neighborhood. In the other municipalities, neighborhood-level shares are not presented as observed data: the detailed distribution uses mapped industrial/commercial locations and service activity associated with residential areas.

3. The formal share is normalized to 62.2% of the workers in the scenario, corresponding to the complement of the metropolitan informality rate of 37.8%. CEMPRE and RAIS do not cover exactly the same statistical universe as PNAD; they are used as **spatial references**, not as counts that can be directly added together.

4. The informal share uses an explicit approximation: 75% of the resident distribution and 25% of the formal employment distribution. The dataset used does not provide observed coordinates for all of these workers.

5. A gravity model adjusts the flows until they satisfy the number of workers at each residential origin and the target number of jobs by region, using road-path travel times. Previous weights derived from the incorrect concentration of jobs in Fundão are not included in the calculation.

Final values are integers. The spreadsheets publish the targets, results, and rounding differences. The report records the largest residual; it does not claim exact equality between every neighborhood quota and the final integer values.

## Interpretation and Limitations

For Registry releases, `package_rio.py` exports demand-point `residents` as the sum of the worker groups originating there. Both demand totals are therefore 5,533,862, while the census population of 11,522,312 remains in the source data, census reports and map configuration. The exported `residents` field represents modeled resident workers, not all inhabitants. Non-workers receive no invented commuting trips; job counts and worker routes are unchanged. Unused anchors with no workers or jobs are omitted from the release. Local raw-data serving/installation scripts still use the census-based source file; use the release ZIP to test the Registry export.

* `employment_by_neighborhood.csv`: neighborhood-level quotas within the municipality of Rio de Janeiro; for other municipalities, the “Total no recorte municipal” (“Total within the municipal study area”) row explicitly identifies the available calibration level.

* `employment_by_municipality.csv`: residents, resident workers, and jobs located within the study area of each municipality. The difference between resident workers and located jobs makes it possible to identify municipalities that primarily generate outbound trips and those that attract trips.

* `data/employment_locations.json`: municipality and neighborhood associated with each demand point.

* `data/employment_audit.json`: periods, rates, weights, and results for this generation.

The game balances the total number of jobs with the total number of resident workers: there is no explicit external flow crossing the map boundary. Employed people are not necessarily passengers who commute every day; remote work, part-time schedules, multiple jobs, vacations, and weekly commuting frequency are not individually discounted. The simulation does not convert all UFRJ students into employees.

Cidade Universitária is accounted for using the RAIS neighborhood polygon. The rectangle previously used included areas on the mainland and should not be interpreted as representing the island.

The generation routine performs the arithmetic checks required for balancing. The test suite and in-game evaluation are left to the user.
