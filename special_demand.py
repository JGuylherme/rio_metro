"""Add auditable non-work trip equivalents to the release, never to census jobs."""
import copy
import hashlib
import json
import math
from datetime import date
from collections import Counter
import numpy as np
from employment import integer_totals
from map_settings import ROOT, DATA, PLAY_BBOX
from release_demand import export_demand

PREFIXES = {'airports': 'AIR_', 'universities': 'UNI_', 'schools': 'SCH_',
            'hospitals': 'HOS_', 'ferries': 'FER_', 'parks': 'PAR_', 'entertainment': 'ENT_'}


def capacity(site):
    """All reductions are named assumptions, not hidden travel measurements."""
    value = site['source_count']
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Source count must be positive')
    if site['basis'] == 'annual':
        days = site['days_per_year']
        if days not in (365, 366):
            raise ValueError('Use calendar-year days for annual activity')
        value /= days
    elif site['basis'] == 'period':
        start=date.fromisoformat(site['period_start'])
        end=date.fromisoformat(site['period_end'])
        days=(end-start).days+1
        if not 1 <= days <= 366:
            raise ValueError('Invalid observed activity period')
        value /= days
    elif site['basis'] not in ('enrollment', 'beds'):
        raise ValueError('Unknown special demand basis')
    for key, factor in site['factors'].items():
        if not math.isfinite(factor) or factor <= 0 or factor > 2:
            raise ValueError('Invalid conversion factor: ' + key)
        value *= factor
    return round(value)


def validate_catalog(catalog):
    ids = set()
    allocations = {}
    for site in catalog['sites']:
        if site['category'] not in PREFIXES or not site['id'].startswith(PREFIXES[site['category']]):
            raise ValueError('Special category/prefix mismatch')
        if site['id'] in ids:
            raise ValueError('Duplicate special destination')
        ids.add(site['id'])
        lon, lat = site['location']
        if not PLAY_BBOX[0] <= lon <= PLAY_BBOX[2] or not PLAY_BBOX[1] <= lat <= PLAY_BBOX[3]:
            raise ValueError('Special destination outside playable area')
        if not site['source_url'].startswith('https://') or not site['assumptions'] or not site['source_year']:
            raise ValueError('Special destination lacks provenance')
        if site['max_distance_m'] <= 0 or site['decay_seconds'] <= 0 or capacity(site) <= 0:
            raise ValueError('Special destination has invalid demand/catchment')
        if site.get('allocation_group'):
            group=site['allocation_group']
            anchor=(site['source_count'],site['source_year'],site['source_url'],site['basis'])
            share_key=site.get('allocation_share_key','campus_share_assumed')
            share=site['factors'][share_key]
            if group in allocations and allocations[group][0] != anchor:
                raise ValueError('Inconsistent institutional count within '+group)
            previous=allocations.get(group,(anchor,0))[1]
            allocations[group]=(anchor,previous+share)
    if any(total > 1+1e-9 for _,total in allocations.values()):
        raise ValueError('Site shares exceed their shared source total')


def add_special_demand(base, catalog, route_provider=None):
    validate_catalog(catalog)
    # Require an unaugmented, balanced export: repeated packaging cannot double demand.
    if any(p['id'].startswith(tuple(PREFIXES.values())) for p in base['points']):
        raise ValueError('Special demand has already been applied')
    base = export_demand(base)
    result = copy.deepcopy(base)
    points = {p['id']: p for p in result['points']}
    homes = [p for p in base['points'] if p['residents'] > 0]
    metadata = {p['id']: p for p in catalog.get('origin_metadata', [])}
    if route_provider is None:
        from road_router import RoadRouter
        router = RoadRouter()
        route_provider = router.to_destination
    totals = Counter()
    report = []
    for site in catalog['sites']:
        if site['id'] in points:
            raise ValueError('Special point collides with base ID')
        allowed = site.get('origin_municipalities')
        eligible = [p for p in homes if not allowed or metadata.get(p['id'], {}).get('municipality_code') in allowed]
        if not eligible:
            raise ValueError('No eligible origins for ' + site['id'])
        routes = route_provider(site['location'], [p['location'] for p in eligible])
        if len(routes) != len(eligible):
            raise ValueError('Router returned wrong origin count')
        candidates = [i for i, route in enumerate(routes) if route is not None and 0 < route[0] <= site['max_distance_m']]
        if not candidates:
            raise ValueError('No road-accessible origins for ' + site['id'])
        weights = np.array([eligible[i]['residents'] * math.exp(-routes[i][1] / site['decay_seconds']) for i in candidates])
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(site['id'].encode()).digest()[:8], 'big'))
        total = capacity(site)
        if len(candidates) > 128:
            # Sample mass once; reweighting weighted samples by population again
            # would inadvertently square the residential attraction weights.
            draws = rng.choice(len(candidates), size=min(128,total), replace=True, p=weights / weights.sum())
            chosen, frequencies = np.unique(draws, return_counts=True)
            candidates = [candidates[i] for i in chosen]
            weights = frequencies
        sizes = integer_totals(weights, total)
        destination = {'id': site['id'], 'location': site['location'], 'residents': 0, 'jobs': total, 'popIds': []}
        for i, size in zip(candidates, sizes):
            if size == 0:
                continue
            home = points[eligible[i]['id']]
            pid = f"SPECIAL_{site['id']}_{home['id']}"
            distance, seconds = routes[i]
            if not math.isfinite(distance) or not math.isfinite(seconds) or distance <= 0 or seconds <= 0:
                raise ValueError('Invalid special route')
            pop = {'id': pid, 'residenceId': home['id'], 'jobId': site['id'], 'size': int(size),
                   'drivingDistance': int(distance), 'drivingSeconds': int(seconds)}
            result['pops'].append(pop)
            home['residents'] += int(size)
            home['popIds'].append(pid)
            destination['popIds'].append(pid)
        result['points'].append(destination)
        points[destination['id']] = destination
        totals[site['category']] += total
        report.append({**site, 'modeled_daily_trip_equivalents': total, 'origin_groups': len(destination['popIds'])})
        print(f"Special demand: {site['name']}: {total:,}", flush=True)
    export_demand(result)  # endpoint, count, and membership integrity
    return result, {'schema_version': 1, 'base_worker_total': sum(p['size'] for p in base['pops']),
                    'source_notes': catalog.get('source_notes', {}),
                    'special_trip_equivalents': sum(totals.values()), 'by_category': dict(sorted(totals.items())),
                    'suggested_registry_tags': sorted(totals), 'sites': report,
                    'interpretation': 'Additional non-work trip equivalents, not unique residents or observed employment. No new workplace employees.'}


def release_with_special_demand(base):
    catalog = json.loads((ROOT / 'special_demand_sites.json').read_text())
    metadata = json.loads((DATA / 'demand_metadata.json').read_text())
    catalog['origin_metadata'] = [{'id': p['id'], 'municipality_code': str(p['sectors'][0])[:7]}
                                  for p in metadata if p.get('sectors')]
    # Route cache includes graph content and ordered endpoints, independent of capacities.
    graph_hash = hashlib.sha256((DATA / 'geography.pkl').read_bytes()).hexdigest()
    cache_path = DATA / 'special_road_routes.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    router = None

    def route(location, origins):
        nonlocal router
        key = hashlib.sha256(json.dumps([graph_hash, location, origins]).encode()).hexdigest()
        if key not in cache:
            from road_router import RoadRouter
            if router is None:
                router = RoadRouter()
            cache[key] = router.to_destination(location, origins)
        return cache[key]

    result, report = add_special_demand(base, catalog, route)
    temporary = cache_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(cache, separators=(',', ':')))
    temporary.replace(cache_path)
    return result, report
