# Special demand — version 2.2.0

The release adds actual commuter groups for seven Registry categories. Merely drawing a hospital, airport or park does not create special demand.

| Registry tag | Modeled destinations |
| --- | --- |
| `airports` | Galeão and Santos Dumont passenger terminals |
| `entertainment` | Museu do Amanhã; Corcovado; Copacabana, Leme, Ipanema, Leblon, Arpoador; BarraShopping, VillageMall, ParkShoppingCampoGrande, ParkJacarepaguá; Maracanã and Nilton Santos |
| `ferries` | Praça XV, Arariboia and Charitas terminal access |
| `hospitals` | HUAP; Bonsucesso; Servidores do Estado; Pedro Ernesto; Getúlio Vargas; Souza Aguiar |
| `parks` | Parque Lage; Floresta da Tijuca access |
| `schools` | CAp-Uerj basic-education pupils |
| `universities` | UFRJ (3); UFF Niterói (3); Uerj Maracanã, FFP and FEBF; PUC-Rio Gávea |

The expanded catalog has 38 destinations and 314,835 non-work trip equivalents,
including separate route contributions at Praça XV. It is not a complete inventory
of metropolitan institutions. Beaches and malls use the supported `entertainment`
tag; there are no invented `beaches` or `shopping` Registry tags.

## Beaches, shopping and stadiums

- Beaches use the [municipal Tourism Yearbook, base 2023, p.15](https://siurb.rio/portal/sharing/rest/content/items/c55ccc425c814f0fae20d990bf1313f1/data).
  These are expanded mobile-phone visitor estimates, including locals and tourists,
  with at least 30 minutes of presence. Summed monthly counts are divided by 365;
  they are not measured daily trips. Copacabana/Leme's shared total is split 85/15%;
  Ipanema/Leblon/Arpoador's shared total is split 65/30/5%. These are spatial
  assumptions, validated so each published group is used exactly once.
- Mall footfall comes from the operator's 2025 technical sheets: [BarraShopping](https://www.multiplan.com.br/shoppings/barrashopping/),
  [VillageMall](https://www.multiplan.com.br/shoppings/villagemall/),
  [ParkShoppingCampoGrande](https://www.multiplan.com.br/shoppings/parkshoppingcampogrande/)
  and [ParkJacarepaguá](https://www.multiplan.com.br/shoppings/parkjacarepagua/).
  Annual visits / 365 produce trip equivalents; New York City Center is not added
  separately to the connected BarraShopping destination.
- Maracanã uses the operator's 2024 match attendance, 3,473,045 / 366. No overlapping
  phone-zone estimate is added. Nilton Santos uses only the documented eight 2024
  Libertadores matches, mean 33,322, from the club's FY2024 report (PDF p.71).
  That is a partial baseline, not total annual stadium attendance. Event peaks
  are smoothed over the year; the game does not schedule the real match calendar.

## Sources and conversion

[special_demand_sites.json](special_demand_sites.json) records each source URL, year, input count, destination coordinates, conversion factors, catchment and assumptions. The generated `dist/special_demand_report.json` records the realized demand and origin-group count for each entry.

- Annual visitor counts are divided by the calendar days of their year: 366 for 2024, 365 for 2019. Each result is an outward-and-return trip equivalent; the game models both legs.
- Airport movement includes arrivals and departures, so it is additionally divided by two. Transfer exclusions are assumptions: 20% for Galeão and 5% for Santos Dumont. Santos Dumont uses the reported rounded 4.9 million movements from January–October 2025, divided by the **304 days actually observed**; it does not substitute the airport's capacity limit for passengers.
- Ferry boarding totals are divided by two, reduced to an explicitly assumed 20% non-work share, then split between the two terminals. Catchments stay on the relevant side of the bay. These are local access trips, not ferry crossings, and do not reroute existing workers.
- HUAP retains 142,000 outpatient consultations in **2019**, plus an assumed 0.5 companion per consultation. The five additional large public hospitals use published bed capacity × assumed 80% occupancy × one visitor per occupied bed/day. Those entries add visitors only; outpatient patients and staff are omitted. These historical capacities are **not a verified ranking of the five largest hospitals in the city**, which would require a consistent CNES snapshot covering public, private and military units. Four bed counts come from the SES-RJ 2019 process annex; Souza Aguiar uses the SMS December 2025 count.
- UFRJ's **2025/2** undergraduate count includes active and paused enrollment. In-map share, daily attendance and campus shares are assumptions; campus shares partition one institutional total. Employees and postgraduate students are not added as undergraduates.
- UFF uses 36,314 Niterói undergraduate registrations from the CPA report (Figure 12, PDF p.47, snapshot 27 April 2024). Assumed shares are Gragoatá 45%, Praia Vermelha 30%, Valonguinho 15%; the remaining 10% in dispersed units is omitted. Distance education and other cities are excluded. Daily attendance is assumed at 70%.
- Uerj uses its approximately 25,000 **2019 in-person undergraduates**, partitioned into Maracanã 75%, FFP São Gonçalo 8% and FEBF Duque de Caxias 4%; other units are omitted, with 70% attendance assumed. PUC uses approximately 10,900 undergraduate/stricto-sensu students in **2023**, with assumed 95% Gávea share and 70% attendance.
- Institution allocation groups are validated: campus shares cannot exceed 100% or mix different source totals.
- CAp-Uerj uses an approximately 1,000-pupil **2022** reference with assumed 90% school-day attendance. School demand is not an annual-average attendance series.
- Corcovado and individual park sectors use separate visitation entries; no park-wide total is added on top of them.

These datasets have different years and precision. Factors, catchments and residential origins are modeled. The layer adds **314,835 daily trip equivalents**, not 314,835 distinct census residents or workers. Origins use residential-worker geography as a proxy; visitor accommodation, student addresses and patient origins are not observed.

## Routing and export

Special groups use directed shortest driving paths from the local OSM road graph, plus explicit access connectors at 20 km/h. Origins or destinations more than 1.5 km from the connected road network are rejected. Each destination is represented by at most 128 origin groups with deterministic sampling. Routes are cached against graph and endpoint hashes.

`AIR_` and `UNI_` use the [game's documented airport and university timing prefixes](https://www.subwaybuilder.com/docs/api-reference/demand). Other categories use ordinary commute timing in this data-only release; no custom leisure, hospital or school timetable is claimed.

Packaging always starts from the worker-only source. It preserves all employment trips, updates both endpoint counts and memberships, and verifies residents = jobs = total pop sizes. Repackaging cannot accumulate a second copy of special demand.

## Registry tags

Use the seven tags listed above when updating the Registry listing. Packaging writes their exact list to `dist/registry_update.json`; that file is review metadata, not a replacement for the release manifest or an automatic Registry submission.

The Registry explicitly excludes special demand from the scored commute pillars. These tags improve map content and discoverability; they do not raise the data-quality tier by themselves.
