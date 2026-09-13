"""Export modeled commuters while retaining census residents in the source data."""
from collections import Counter, defaultdict


def export_demand(demand):
    points = {p['id']: p for p in demand['points']}
    if len(points) != len(demand['points']):
        raise ValueError('Duplicate demand point ID')
    homes, jobs = Counter(), Counter()
    members = defaultdict(set)
    seen = set()
    for pop in demand['pops']:
        pid, home, job, size = (pop[k] for k in ('id', 'residenceId', 'jobId', 'size'))
        if pid in seen or home not in points or job not in points:
            raise ValueError('Duplicate pop ID or unknown endpoint: '+str(pid))
        if type(size) is not int or size <= 0:
            raise ValueError('Invalid pop size: '+str(pid))
        seen.add(pid)
        homes[home] += size
        jobs[job] += size
        members[home].add(pid)
        members[job].add(pid)
    exported = []
    for pid, point in points.items():
        if point['residents'] < homes[pid] or point['jobs'] != jobs[pid]:
            raise ValueError('Inconsistent census/worker/job counts: '+pid)
        if len(point['popIds']) != len(set(point['popIds'])) or set(point['popIds']) != members[pid]:
            raise ValueError('Inconsistent pop membership: '+pid)
        # Unused anchors are not demand points in the release format.
        if homes[pid] or jobs[pid]:
            exported.append({**point, 'residents': homes[pid]})
    result = {**demand, 'points': exported}
    if sum(p['residents'] for p in exported) != sum(p['size'] for p in demand['pops']):
        raise ValueError('Release resident totals mismatch')
    return result
