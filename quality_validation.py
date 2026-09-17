"""Independent accounting and spatial diagnostics for the quality upgrade."""
from collections import Counter,defaultdict
import json
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box,shape
from shapely.strtree import STRtree
from map_settings import ROOT,DATA,PLAY_BBOX
from quality_placement import water_geometry


def metrics(actual,reference):
    a=np.asarray(actual,float);b=np.asarray(reference,float);delta=a-b;valid=b>0
    return {'mae':float(np.abs(delta).mean()),'rmse':float(np.sqrt(np.mean(delta**2))),
        'mape_nonzero_percent':float(np.mean(np.abs(delta[valid]/b[valid]))*100) if valid.any() else None,
        'correlation':float(np.corrcoef(a,b)[0,1]) if a.std()>0 and b.std()>0 else None}


def validate(demand,flows,codes,employed,workers,jobs,od,home_mun,placement,coverage,reports):
    points=demand['points'];index={p['id']:p for p in points}
    if len(index)!=len(points):raise ValueError('Duplicate point IDs')
    origins=Counter();destinations=Counter();members=defaultdict(set);seen=set()
    for p in demand['pops']:
        if p['id'] in seen:raise ValueError('Duplicate flow ID')
        seen.add(p['id'])
        if p['residenceId'] not in index or p['jobId'] not in index:raise ValueError('Missing endpoint')
        if any(not isinstance(p[k],int) or p[k]<=0 for k in ['size','drivingDistance','drivingSeconds']):raise ValueError('Invalid flow value')
        origins[p['residenceId']]+=p['size'];destinations[p['jobId']]+=p['size']
        members[p['residenceId']].add(p['id']);members[p['jobId']].add(p['id'])
    for p in points:
        if origins[p['id']]>p['residents'] or destinations[p['id']]!=p['jobs']:raise ValueError('Endpoint mass mismatch')
        if set(p['popIds'])!=members[p['id']] or len(p['popIds'])!=len(members[p['id']]):raise ValueError('Invalid membership')
    positions=shapely.points([p['location'] for p in points])
    if not np.all(shapely.covers(box(*PLAY_BBOX),positions)):raise ValueError('Point outside playable boundary')
    wet=shapely.covers(water_geometry(),positions)
    warnings=[]
    if wet.any():
        # Old residential anchors are retained only when no address exists. Report
        # those explicitly; new workplace locations must always be on land.
        ids=[p['id'] for p,w in zip(points,wet) if w]
        if any(index[p]['jobs'] for p in ids):raise ValueError('Workplaces in water: '+str(ids))
        warnings.append({'kind':'residential_water_overlap','points':ids})
    actual=flows.groupby(['origin','destination'])['size'].sum().unstack(fill_value=0).reindex(index=codes,columns=codes,fill_value=0).to_numpy()
    if not np.array_equal(actual,od):raise ValueError('Municipal OD not preserved by fine disaggregation')
    if not np.array_equal(actual.sum(axis=1),workers) or not np.array_equal(actual.sum(axis=0),jobs):raise ValueError('Municipal margins mismatch')
    targets=pd.read_csv(reports/'od_municipal_targets.csv',dtype={'origin':str,'destination':str})
    targets['actual']=actual.ravel();targets['target_error']=targets.actual-targets.balanced_target
    targets['difference_from_historical_2010']=targets.actual-targets.observed_2010_expanded
    targets['historical_change_percent']=np.where(targets.observed_2010_expanded>0,100*targets.difference_from_historical_2010/targets.observed_2010_expanded,np.nan)
    targets.to_csv(reports/'od_comparison.csv',index=False)
    targets.to_csv(ROOT/'commuting_comparison.csv',index=False)
    comparison={'balanced_target':metrics(actual.ravel(),od.ravel()),
        'historical_2010_change_NOT_validation_of_2022_pairs':metrics(targets.actual,targets.observed_2010_expanded),
        'observed_2022_pairs_available':False}
    (reports/'od_metrics.json').write_text(json.dumps(comparison,indent=2)+'\n')
    # Independently reconstruct source population by sector, rather than trusting
    # the newly placed residential points.
    allocation=pd.read_csv(DATA/'census_allocation.csv',dtype={'sector':str})
    source_pop=allocation.groupby(allocation.sector.str[:7]).assigned_population.sum()
    homes=[p for p in points if p['residents']>0]
    pop=np.array([p['residents'] for p in homes]);mun=np.asarray(home_mun)
    rais=pd.read_parquet(DATA/'quality_prepared/rais_postal_activity.parquet').groupby('municipality').active_links.sum()
    cempre={r['D1C']:float(r['V']) for r in json.loads((DATA/'employment_sources/cempre_current.json').read_text())[1:] if r['D2C']=='707' and r['V'] not in ['-','...','X']}
    universe=pd.read_csv(reports/'commuter_universe.csv',dtype={'municipality_code':str}).set_index('municipality_code')
    names=pd.read_pickle(DATA/'census.pkl').drop_duplicates('CD_MUN').set_index('CD_MUN').NM_MUN.to_dict()
    rows=[]
    for i,code in enumerate(codes):
        represented=int(pop[mun==code].sum());expected=int(source_pop[code])
        out=actual[i].copy();out[i]=0;inbound=actual[:,i].copy();inbound[i]=0
        rows.append({'municipality_code':code,'municipality':names.get(code,code),
            'census_population_in_map':expected,'population_in_map':represented,'population_error':represented-expected,
            'population_error_percent':100*(represented-expected)/expected if expected else 0,
            'employed_pnad_calibrated':int(employed[i]),'commuter_target':int(workers[i]),'commuters_in_map':int(actual[i].sum()),
            'commuter_error':int(actual[i].sum()-workers[i]),'excluded_home_external_multiple_boundary':int(employed[i]-workers[i]),
            'rais_2024_full_municipality_links':int(rais.get(code,0)),
            'rais_in_map_placed_weight':float(rais.get(code,0)*coverage.get(code,0)),
            'cempre_2024_full_municipality_persons':cempre.get(code),
            'modeled_jobs':int(jobs[i]),'realized_jobs':int(actual[:,i].sum()),'job_target_error':int(actual[:,i].sum()-jobs[i]),
            'job_reconciliation_from_raw_weight':int(universe.loc[code,'job_target_adjustment']),
            'incoming_intermunicipal':int(inbound.sum()),'outgoing_intermunicipal':int(out.sum()),
            'top_destinations':'; '.join(f'{names.get(codes[j],codes[j])}:{int(out[j])}' for j in np.argsort(-out)[:3] if out[j]),
            'top_origins':'; '.join(f'{names.get(codes[j],codes[j])}:{int(inbound[j])}' for j in np.argsort(-inbound)[:3] if inbound[j])})
    frame=pd.DataFrame(rows)
    if frame.population_error.abs().sum():raise ValueError('Census population changed')
    frame.to_csv(reports/'municipal_validation.csv',index=False)
    frame.to_csv(ROOT/'employment_by_municipality.csv',index=False)
    # No assertion of agreement between raw RAIS links/CEMPRE persons and model
    # commuters: these cover different statistical universes.
    weights=flows['size'].to_numpy()
    hist=[]
    for column,edges in [('distance_m',[0,5000,10000,20000,40000,60000,100000,np.inf]),('seconds',[0,900,1800,3600,5400,7200,np.inf])]:
        values=flows[column].to_numpy()
        for lower,upper in zip(edges[:-1],edges[1:]):
            count=int(weights[(values>=lower)&(values<upper)].sum())
            hist.append({'measure':column,'lower':lower,'upper':upper,'commuters':count,'share':count/weights.sum()})
    pd.DataFrame(hist).to_csv(reports/'travel_distribution.csv',index=False)
    from quality_travel_validation import compare
    compare(flows,reports)
    # Data-derived centralities use the existing official bairro polygons.
    features=json.loads((DATA/'employment_sources/rais_bairros_2023.geojson').read_text())['features']
    features=[f for f in features if f['geometry']]
    geoms=np.array([shape(f['geometry']) for f in features],object);tree=STRtree(geoms)
    labels={p['id']:str(c) for p,c in zip(homes,home_mun)}
    labels.update(dict(zip(placement.id,placement.municipality_code.astype(str))))
    point_rows=[]
    for p,pos in zip(points,positions):
        code=labels[p['id']];name='Municipal total'
        if code=='3304557':
            matches=tree.query(pos,predicate='intersects')
            name=features[int(matches[0])]['properties']['nome'] if len(matches) else 'Outside bairro polygons'
        point_rows.append({'id':p['id'],'municipality_code':code,'municipality':names.get(code,code),'bairro':name,
            'residents':p['residents'],'resident_workers':origins[p['id']],'jobs':p['jobs'],
            'lon':p['location'][0],'lat':p['location'][1]})
    spatial=pd.DataFrame(point_rows)
    grouped=spatial.groupby(['municipality_code','municipality','bairro'])[['residents','resident_workers','jobs']].sum()
    grouped['jobs_per_resident']=grouped.jobs/grouped.residents.replace(0,np.nan)
    # Density uses actual polygon area, clipped to the map; it is not jobs
    # divided by the footprint of the single representative aggregation point.
    census=pd.read_pickle(DATA/'census.pkl')
    muni_area=census[['CD_MUN','geometry']].dissolve(by='CD_MUN').clip(box(*PLAY_BBOX)).to_crs(31983).area/1e6
    areas={str(k):float(v) for k,v in muni_area.items()}
    from pyproj import Transformer
    from shapely.ops import transform
    project=Transformer.from_crs(4326,31983,always_xy=True).transform
    bairro_area={f['properties']['nome']:transform(project,shape(f['geometry']).intersection(box(*PLAY_BBOX))).area/1e6 for f in features}
    grouped['covered_area_km2']=[bairro_area.get(b,areas.get(c,0)) if c=='3304557' else areas.get(c,0) for c,_,b in grouped.index]
    grouped['jobs_per_km2']=grouped.jobs/grouped.covered_area_km2.replace(0,np.nan)
    grouped['residents_per_km2']=grouped.residents/grouped.covered_area_km2.replace(0,np.nan)
    grouped.to_csv(reports/'centralities.csv');grouped.to_csv(ROOT/'employment_by_neighborhood.csv')
    spatial.to_csv(reports/'point_distribution.csv',index=False)
    high=spatial[spatial.jobs>20000]
    if len(high):warnings.append({'kind':'aggregated_workplace_over_20000','points':high[['id','jobs']].to_dict('records'),
        'meaning':'Aggregates multiple addresses; not verified single-building capacities. Inspect workplace_placement.csv.'})
    access=pd.read_csv(reports/'road_access.csv')
    if access.over_1500m.any():warnings.append({'kind':'long_road_connectors','points':int(access.over_1500m.sum()),'max_m':float(access.road_connector_m.max())})
    long=int(weights[flows.seconds.to_numpy()>7200].sum())
    if long:warnings.append({'kind':'road_trips_over_two_hours','commuters':long})
    (reports/'warnings.json').write_text(json.dumps(warnings,indent=2)+'\n')
    addresses=pd.read_parquet(DATA/'quality_prepared/workplace_addresses.parquet')
    extents=addresses.groupby(['municipality','cep']).agg(lon_min=('lon','min'),lon_max=('lon','max'),lat_min=('lat','min'),lat_max=('lat','max'),units=('unit_id','size'))
    extents['bounding_diagonal_m']=np.hypot((extents.lon_max-extents.lon_min)*102400,(extents.lat_max-extents.lat_min)*111132)
    calibration=pd.read_csv(reports/'rais_postal_calibration.csv',dtype={'municipality_code':str,'cep':str})
    calibration=calibration.merge(extents.reset_index(),left_on=['municipality_code','cep'],right_on=['municipality','cep'],how='left')
    calibration.to_csv(reports/'postal_grain_diagnostics.csv',index=False)
    postal=calibration.method.str.startswith('postal_')
    grain={'postal_matched_share':float(calibration.loc[postal,'rais_active_links'].sum()/calibration.rais_active_links.sum()),
        'municipal_fallback_share':float(calibration.loc[~postal,'rais_active_links'].sum()/calibration.rais_active_links.sum()),
        'postal_with_address_extent_over_5km_links_share':float(calibration.loc[postal & calibration.bounding_diagonal_m.gt(5000),'rais_active_links'].sum()/calibration.rais_active_links.sum()),
        'interpretation':'CEP counts are observed; address coordinates and class matches are allocation support, not identified RAIS establishments. Wide postal areas and municipal fallbacks limit effective grain.'}
    (reports/'postal_grain_summary.json').write_text(json.dumps(grain,indent=2)+'\n')
    return {'municipalities':len(codes),'points':len(points),'municipal_od_max_error':int(np.max(abs(actual-od))),
        'warnings':warnings,'road_distance_weighted_mean_m':float(np.average(flows.distance_m,weights=weights)),
        'road_seconds_weighted_mean':float(np.average(flows.seconds,weights=weights)),
        'intramunicipal_commuters':int(np.trace(actual)),'intermunicipal_commuters':int(actual.sum()-np.trace(actual))}
