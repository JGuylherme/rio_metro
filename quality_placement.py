"""CNEFE dwelling anchors and RAIS postal/activity-constrained workplace weights."""
from collections import Counter
from functools import lru_cache
import json
import pickle
import inspect
import numpy as np
import pandas as pd
import duckdb
import shapely
from shapely.geometry import shape,box
from shapely.ops import unary_union
from scipy.spatial import cKDTree
from census_workers import allocate_workers
from employment import integer_totals
from geography import PROJECT
from map_settings import ROOT,DATA,PLAY_BBOX

PREP=DATA/'quality_prepared'


@lru_cache(maxsize=1)
def water_geometry():
    surfaces,*_=pickle.loads((DATA/'geography.pkl').read_bytes())
    water=unary_union([shape(f['geometry']) for layer,f in surfaces if layer=='water'])
    shapely.prepare(water)
    return water


def residential_anchors(points, metadata, reports):
    """One existing performance anchor, selected from observed dwelling addresses."""
    homes=[p.copy() for p in points if p['residents']>0]
    lineage=pd.DataFrame([(m['id'],str(sector)) for m in metadata if m.get('sectors') for sector in m['sectors']],columns=['point_id','sector'])
    if lineage.sector.duplicated().any():raise ValueError('Duplicate residential sector lineage')
    connection=duckdb.connect();connection.execute("SET memory_limit='1GB'")
    connection.register('lineage',lineage)
    path=str(PREP/'cnefe_units.parquet')
    west,south,east,north=PLAY_BBOX
    chosen=connection.execute('''WITH units AS (
        SELECT DISTINCT unit_id, species, l.point_id, u.sector, lon, lat, geo_level, building_type
        FROM read_parquet(?) u JOIN lineage l USING(sector)
        WHERE species=1 AND geo_level IN (1,2,3) AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?),
        centers AS (SELECT *,avg(lon) OVER(PARTITION BY point_id) cx, avg(lat) OVER(PARTITION BY point_id) cy,
            count(*) OVER(PARTITION BY point_id) dwelling_units FROM units),
        ranked AS (SELECT *,row_number() OVER(PARTITION BY point_id ORDER BY
            pow((lon-cx)*0.92,2)+pow(lat-cy,2),geo_level,unit_id) rn FROM centers)
        SELECT * FROM ranked WHERE rn<=12''',[path,west,east,south,north]).df()
    connection.close()
    water=water_geometry()
    chosen=chosen[~shapely.covers(water,shapely.points(chosen.lon,chosen.lat))]
    chosen=chosen.sort_values(['point_id','rn']).drop_duplicates('point_id').set_index('point_id')
    rows=[];lookup={m['id']:m.copy() for m in metadata}
    for point in homes:
        old=point['location'];meta=lookup[point['id']]
        if point['id'] in chosen.index:
            row=chosen.loc[point['id']];point['location']=[float(row.lon),float(row.lat)]
            meta.update(location_method='CNEFE dwelling-unit anchor; original census-unit counts and aggregation retained',
                cnefe_dwelling_units=int(row.dwelling_units),cnefe_geo_level=int(row.geo_level),cnefe_unit_id=str(row.unit_id))
        else:meta['cnefe_fallback']='No usable matched dwelling unit; retained existing census/footprint anchor'
        rows.append({'id':point['id'],'municipality_code':str(meta['sectors'][0])[:7],
            'population':point['residents'],'cnefe_matched':point['id'] in chosen.index,
            'dwelling_units':meta.get('cnefe_dwelling_units',0),'geo_level':meta.get('cnefe_geo_level'),
            'old_lon':old[0],'old_lat':old[1],'lon':point['location'][0],'lat':point['location'][1]})
        point['jobs']=0;point['popIds']=[]
    pd.DataFrame(rows).to_csv(reports/'residential_placement.csv',index=False)
    return homes,[lookup[p['id']] for p in homes]


def workers_pnad(homes, metadata, reports):
    # allocate_workers reads the unchanged census-sector lineage/counts from DATA.
    municipality=np.array([str(m['sectors'][0])[:7] for m in metadata])
    workers,info=allocate_workers(homes,municipality,age_output=reports/'resident_age_structure.csv')
    census_workers=workers.copy();population=np.array([p['residents'] for p in homes])
    folder=DATA/'employment_sources'
    pnad=json.loads((folder/'pnad_current.json').read_text())[1:]
    population_control=json.loads((folder/'population_current.json').read_text())[1:]
    vals={(r['D1C'],r['D2C']):float(r['V']) for r in pnad};den={r['D1C']:float(r['V']) for r in population_control}
    rates={'capital':vals['3304557','4090']/den['3304557'],
        'metropolitan_remainder':(vals['3301','4090']-vals['3304557','4090'])/(den['3301']-den['3304557']),
        'state_proxy':vals['33','4090']/den['33']}
    metropolitan={'3300456','3301702','3301850','3301900','3302007','3302270','3302502','3302700','3302858','3303203','3303302','3303500','3303609','3304144','3304557','3304904','3305109','3305554'}
    strata=np.array(['capital' if m=='3304557' else 'metropolitan_remainder' if m in metropolitan else 'state_proxy' for m in municipality])
    controls=[]
    for stratum,rate in rates.items():
        ids=np.flatnonzero(strata==stratum);target=round(population[ids].sum()*rate)
        workers[ids]=integer_totals(census_workers[ids],target)
        controls.append({'stratum':stratum,'census_population_2022':int(population[ids].sum()),'pnad_occupied_over_all_age_population':rate,
            'census_employed_2022_covered':int(census_workers[ids].sum()),'calibrated_employed':target,
            'factor_over_census':target/census_workers[ids].sum()})
    if np.any(workers>population):raise ValueError('PNAD-calibrated employment exceeds residents')
    pd.DataFrame(controls).to_csv(reports/'pnad_resident_controls.csv',index=False)
    pd.DataFrame({'id':[p['id'] for p in homes],'municipality_code':municipality,'population':population,
        'census_worker_estimate':census_workers,'employed_pnad_calibrated':workers,'non_employed_estimated':population-workers}).to_csv(reports/'resident_workers.csv',index=False)
    return workers,municipality,vals['3301','12466']/100,info


def workplace_addresses(reports):
    cached=PREP/'workplace_addresses.parquet'
    from quality_cache import fingerprint
    signature=fingerprint([PREP/'cnefe_units.parquet',PREP/'rais_postal_activity.parquet',DATA/'buildings.pkl',DATA/'geography.pkl'],inspect.getsource(workplace_addresses))
    stamp=cached.with_suffix('.sha256')
    report_names=['rais_postal_calibration.csv','workplace_water_exclusions.csv']
    if cached.exists() and stamp.exists() and stamp.read_text()==signature and all((PREP/name).exists() for name in report_names):
        import shutil
        for name in report_names:shutil.copyfile(PREP/name,reports/name)
        return pd.read_parquet(cached)
    connection=duckdb.connect()
    data=connection.execute('''SELECT DISTINCT unit_id,municipality,sector,cep,species,geo_level,lon,lat,activity
        FROM read_parquet(?) WHERE species IN (3,4,5,6,8) AND geo_level IN (1,2,3)''',[str(PREP/'cnefe_units.parquet')]).df()
    connection.close()
    wet=shapely.covers(water_geometry(),shapely.points(data.lon,data.lat))
    pd.DataFrame([{'excluded_water_units':int(wet.sum()),'candidate_units':len(data)}]).to_csv(reports/'workplace_water_exclusions.csv',index=False)
    data=data[~wet].reset_index(drop=True)
    buildings=pd.read_pickle(DATA/'buildings.pkl')
    anchors=shapely.point_on_surface(buildings.geometry.to_numpy())
    xy=np.column_stack(PROJECT(shapely.get_x(anchors),shapely.get_y(anchors)))
    access,indices=cKDTree(xy).query(np.column_stack(PROJECT(data.lon.to_numpy(),data.lat.to_numpy())))
    # A nearby footprint is complementary geometry, not an asserted address join.
    matched=access<=75
    area=shapely.area(buildings.geometry.to_numpy())*111132**2*np.cos(np.radians(-22.85))
    volume=np.clip(area*np.clip(buildings.height.to_numpy()/3,1,40),8,500000)
    units_per_building=np.bincount(indices[matched],minlength=len(buildings))
    data['floor_area_proxy']=np.where(matched,volume[indices]/np.maximum(1,units_per_building[indices]),1.)
    data['building_distance_m']=access;data['building_use']=np.where(matched,buildings['use'].astype(str).to_numpy()[indices],'unmatched')
    use_to_activity={'industrial':'industry','manufacturing':'industry','warehouse':'wholesale','hospital':'health',
        'school':'education','university':'education','retail':'retail','hotel':'hotel','office':'office'}
    inferred=data.building_use.map(use_to_activity)
    use=(data.activity=='other')&inferred.notna();data.loc[use,'activity']=inferred[use]
    data['formal_links']=0.
    rais=pd.read_parquet(PREP/'rais_postal_activity.parquet')
    rais=rais.groupby(['municipality','cep','activity']).active_links.sum().reset_index()
    postal_type=data.groupby(['municipality','cep','activity']).indices
    municipal_type=data.groupby(['municipality','activity']).indices
    postal=data.groupby(['municipality','cep']).indices
    municipal=data.groupby('municipality').indices
    audit=[];weights=data.floor_area_proxy.to_numpy();formal=np.zeros(len(data))
    for row in rais.itertuples(index=False):
        candidates=postal_type.get((row.municipality,row.cep,row.activity));method='postal_activity'
        if candidates is None:
            candidates=postal_type.get((row.municipality,row.cep,'other'));method='postal_unclassified_establishments'
        if candidates is None:
            candidates=municipal_type.get((row.municipality,row.activity));method='municipal_activity_fallback'
        if candidates is None:
            candidates=municipal_type.get((row.municipality,'other'));method='municipal_unclassified_fallback'
        if candidates is None:
            candidates=municipal.get(row.municipality);method='municipal_all_establishments_fallback'
        if candidates is None:raise ValueError('No CNEFE establishments for '+row.municipality)
        w=weights[candidates];allocation=row.active_links*w/w.sum();formal[candidates]+=allocation
        audit.append({'municipality_code':row.municipality,'cep':row.cep,'activity':row.activity,'rais_active_links':int(row.active_links),
            'candidate_address_units':len(candidates),'floor_area_proxy':float(w.sum()),'fitted_links_per_proxy_area':row.active_links/w.sum(),'method':method})
    if abs(formal.sum()-rais.active_links.sum())>.001:raise ValueError('RAIS mass lost')
    data['formal_links']=formal
    pd.DataFrame(audit).to_csv(reports/'rais_postal_calibration.csv',index=False)
    data.to_parquet(cached,index=False)
    import shutil
    for name in report_names:shutil.copyfile(reports/name,PREP/name)
    stamp.write_text(signature)
    return data


def workplace_points(addresses, homes, home_municipality, informal, informal_shares, config, reports):
    west,south,east,north=PLAY_BBOX
    inside=addresses.lon.between(west,east)&addresses.lat.between(south,north)
    full=addresses.groupby('municipality').formal_links.sum()
    covered=addresses.loc[inside].groupby('municipality').formal_links.sum()
    coverage={code:float(covered.get(code,0)/value) if value else 0 for code,value in full.items()}
    data=addresses[inside].copy().reset_index(drop=True)
    # Informal locations are an activity-compatible proxy, not additional formal establishments.
    data['informal_weight']=0.
    for kind,share in informal_shares.items():
        ids=data.index[data.activity==kind].to_numpy()
        if len(ids):data.loc[ids,'informal_weight']+=share/len(ids)
    # Domestic work/construction take place at homes; add weighted dwelling anchors explicitly.
    residential_share=sum(informal_shares.get(k,0) for k in ('domestic','construction'))
    # Those two categories are not also allocated to business offices.
    for kind in ('domestic','construction'):data.loc[data.activity==kind,'informal_weight']=0.
    residential=pd.DataFrame({'unit_id':[p['id'] for p in homes],'municipality':home_municipality,
        'lon':[p['location'][0] for p in homes],'lat':[p['location'][1] for p in homes],
        'formal_links':0.,'informal_weight':np.array([p['residents'] for p in homes],float)/sum(p['residents'] for p in homes)*residential_share,
        'activity':'domestic_construction','geo_level':0,'species':1,'floor_area_proxy':0.,'building_use':'residential'})
    data=pd.concat([data,residential],ignore_index=True)
    if data.informal_weight.sum()<=0:raise ValueError('No informal activity support')
    # Keep the PNAD aggregate share exact in the pre-OD destination weights.
    data['weight']=(1-informal)*data.formal_links/data.formal_links.sum()+informal*data.informal_weight/data.informal_weight.sum()
    data=data[data.weight>0].copy()
    x,y=PROJECT(data.lon.to_numpy(),data.lat.to_numpy());data['x']=x;data['y']=y
    cell=config['workplace_grid_m']
    while True:
        data['gx']=np.floor(x/cell).astype(int);data['gy']=np.floor(y/cell).astype(int)
        grouped=data.groupby(['municipality','gx','gy'],sort=True)
        if grouped.ngroups<=config['maximum_workplace_points']:break
        cell+=100
    points=[];rows=[]
    for (municipality,gx,gy),group in grouped:
        # Select an actual address, never a weighted centroid in water.
        center=np.average(group[['x','y']],axis=0,weights=group.weight)
        candidates=group[group.formal_links>0] if group.formal_links.sum()>0 else group
        chosen=candidates.iloc[np.argmin(np.square(candidates.x-center[0])+np.square(candidates.y-center[1]))]
        pid=f'WRK_{len(points):04d}'
        points.append({'id':pid,'location':[float(chosen.lon),float(chosen.lat)],'residents':0,'jobs':0,'popIds':[]})
        formal=float(group.formal_links.sum());informal_weight=float(group.informal_weight.sum())
        rows.append({'id':pid,'municipality_code':municipality,'formal_links_2024_weight':formal,
            'informal_spatial_weight':informal_weight,'weight':float(group.weight.sum()),'address_units':len(group),
            'representative_unit':str(chosen.unit_id),'representative_activity':str(chosen.activity),
            'grid_m':cell,'lon':chosen.lon,'lat':chosen.lat})
    frame=pd.DataFrame(rows);frame.to_csv(reports/'workplace_placement.csv',index=False)
    return points,frame,coverage
