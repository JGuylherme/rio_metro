"""Measured age structure by census tract, calibrated to municipal employed residents.

The 15–59 band uses complete published bins, without inventing a 60–64 split.
It is a residential proxy, not a claim of measured employed people per tract.
"""
import json
import numpy as np
import pandas as pd
from map_settings import ROOT, DATA

AGE_COLUMNS = [f'V{i:05d}' for i in range(1034, 1040)]


def municipal_series(path, category=None):
    data = json.loads(path.read_text())
    values = {}
    for result in data[0]['resultados']:
        if category is not None and not any(
            str(category) in item['categoria'] for item in result['classificacoes']
        ):
            continue
        for row in result['series']:
            value = row['serie']['2022']
            if value == '-':
                value = '0'  # SIDRA: numerical zero, not privacy suppression.
            if not value.isdigit():
                raise ValueError(f'Suppressed/non-numeric municipal count: {row}')
            code = row['localidade']['id']
            if code in values:
                raise ValueError('Ambiguous municipal series: ' + code)
            values[code] = int(value)
    if not values:
        raise ValueError('Empty census municipal series')
    return values


def allocate_workers(points, municipality, age_output=None):
    from employment import integer_totals
    sources = ROOT / 'sources'
    census = pd.read_csv(sources / 'census_demography_rj_2022.csv', dtype=str).set_index('CD_setor')
    counts = census[AGE_COLUMNS + ['V01006']].replace('-', '0').apply(pd.to_numeric, errors='coerce')
    # Public tract totals are available even where demographic breakdowns are suppressed.
    import pyogrio
    full = pyogrio.read_dataframe(DATA / 'RJ_setores_CD2022.gpkg', columns=['CD_SETOR', 'v0001'], read_geometry=False)
    full = full.drop_duplicates('CD_SETOR').set_index('CD_SETOR').v0001
    counts['V01006'] = counts.V01006.fillna(full.reindex(counts.index))
    counts['age'] = counts[AGE_COLUMNS].sum(axis=1, min_count=len(AGE_COLUMNS))
    codes = counts.index.str[:7]
    known = counts.age.notna() & counts.V01006.gt(0)
    ratio = (counts.loc[known].groupby(codes[known]).age.sum()
             / counts.loc[known].groupby(codes[known]).V01006.sum())
    # Suppression is explicit and quantified; only missing cells use this proxy.
    counts['proxy_age'] = counts.age.fillna(counts.V01006 * codes.map(ratio))
    if counts.proxy_age.isna().any():
        raise ValueError('Missing population denominator for demographic suppression')
    full_age = counts.groupby(codes).proxy_age.sum()
    observed = municipal_series(sources / 'census_workers_2022.json')
    metadata = {p['id']: p for p in json.loads((DATA / 'demand_metadata.json').read_text())}
    allocation = pd.read_csv(DATA / 'census_allocation.csv', dtype={'sector': str}).set_index('sector')
    if allocation.index.has_duplicates:
        raise ValueError('A census sector was allocated more than once')
    age = np.zeros(len(points))
    suppressed_population = 0
    represented_sectors = set()
    rows = []
    for i, point in enumerate(points):
        if not point['residents']:
            continue
        meta = metadata[point['id']]
        assigned = 0
        for sector in meta['sectors']:
            sector = str(sector)
            if sector in represented_sectors:
                raise ValueError('Census sector appears in multiple demand anchors: ' + sector)
            represented_sectors.add(sector)
            a = allocation.loc[sector]
            assigned += int(a.assigned_population)
            if sector[:7] != str(municipality[i]):
                raise ValueError('Residential anchor crossed a municipal boundary')
            measured = sector in counts.index and pd.notna(counts.loc[sector, 'age'])
            if measured:
                value = float(counts.loc[sector, 'age']) * float(a.boundary_fraction)
            else:
                suppressed_population += int(a.assigned_population)
                value = float(a.assigned_population) * float(ratio[sector[:7]])
            age[i] += value
        if assigned != point['residents']:
            raise ValueError('Stale census metadata for ' + point['id'])
        if not 0 <= age[i] <= point['residents'] + 1:
            raise ValueError('Age count incompatible with census total: ' + point['id'])
    residents = np.array([p['residents'] for p in points])
    suppression = suppressed_population / residents.sum()
    if suppression > .05:
        raise ValueError('Age suppression exceeds 5% of represented population')
    workers = np.zeros(len(points), dtype=int)
    for code in sorted(set(municipality)):
        ids = np.flatnonzero(municipality == code)
        coverage = min(1., float(age[ids].sum() / full_age[code]))
        target = round(observed[code] * coverage)
        workers[ids] = integer_totals(age[ids], target)
        if np.any(workers[ids] > residents[ids]):
            raise ValueError('Workers exceed population in municipality ' + code)
        rows.append({'municipality_code': code, 'census_employed_14_plus': observed[code],
                     'age_15_59_in_map': float(age[ids].sum()), 'age_15_59_full_municipality': float(full_age[code]),
                     'coverage_proxy': coverage, 'modeled_workers': target})
    pd.DataFrame(rows).to_csv(ROOT / 'resident_workers_by_municipality.csv', index=False)
    if age_output is not None:
        pd.DataFrame({'id':[p['id'] for p in points],'municipality_code':municipality,
            'census_population':residents,'age_15_59_measured_or_suppression_proxy':age,
            'census_municipal_employment_calibrated':workers}).to_csv(age_output,index=False)
    info = {'resident_count_anchor': 'Census 2022 measured age 15–59 by tract, calibrated to municipal employed age 14+',
            'resident_age_variables': AGE_COLUMNS, 'resident_workers_table': 10261,
            'resident_age_suppressed_population': int(suppressed_population),
            'resident_age_suppressed_population_share': float(suppression),
            'resident_tract_counts_are_employed_counts': False,
            'partial_municipality_coverage': 'share of age 15–59 population; not observed employment coverage',
            'resident_age_points': int(np.count_nonzero(age)), 'resident_age_sectors': len(represented_sectors)}
    return workers, info


def audit_commuting(points, pops, municipality):
    """Compare synthetic flows to survey containment; do not claim enforced O/D."""
    sources = ROOT / 'sources'
    local = municipal_series(sources / 'census_commuting_2022.json', 12167)
    elsewhere = municipal_series(sources / 'census_commuting_2022.json', 12188)
    index = {p['id']: i for i, p in enumerate(points)}
    totals, staying = {}, {}
    for pop in pops:
        origin = municipality[index[pop['residenceId']]]
        destination = municipality[index[pop['jobId']]]
        totals[origin] = totals.get(origin, 0) + pop['size']
        if origin == destination:
            staying[origin] = staying.get(origin, 0) + pop['size']
    rows = []
    for code, total in sorted(totals.items()):
        observed = local[code] / (local[code] + elsewhere[code])
        modeled = staying.get(code, 0) / total
        rows.append({'municipality_code': code, 'observed_local_share_2022': observed,
                     'modeled_local_share': modeled, 'difference_percentage_points': 100 * (modeled - observed),
                     'note': 'Diagnostic only; different universes, external commuting omitted; not an OD constraint'})
    pd.DataFrame(rows).to_csv(ROOT / 'commuting_comparison.csv', index=False)
