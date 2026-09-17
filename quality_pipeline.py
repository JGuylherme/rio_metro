"""Upgrade demand in place, preserving the map's existing geometry and census totals."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from employment import integer_totals
from geography import PROJECT
from map_settings import ROOT,DATA,OUT
from quality_od import fit_sparse,round_transport,municipal_model
from quality_placement import residential_anchors,workers_pnad,workplace_addresses,workplace_points
from quality_pnad import informal_composition
from road_router import RoadRouter


def digest(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def balanced_dense(seed,rows,cols):
    i,j=np.indices(seed.shape);i=i.ravel();j=j.ravel()
    v=fit_sparse(i,j,seed.ravel(),rows,cols)
    return round_transport(i,j,v,rows,cols).reshape(seed.shape)


def fine_flows(homes,workplaces,home_mun,placement,workers,jobs,codes,od,config,reports):
    """Fix municipal pairs first, then solve road-time gravity within each destination."""
    hxy=np.column_stack(PROJECT(*np.array([p['location'] for p in homes]).T))
    jxy=np.column_stack(PROJECT(*np.array([p['location'] for p in workplaces]).T))
    workmun=placement.municipality_code.astype(str).to_numpy()
    quotas=np.zeros((len(homes),len(codes)),dtype=int)
    point_jobs=np.zeros(len(workplaces),dtype=int)
    # The municipal OD table is already fixed. This stage only shares its quotas
    # between homes, before road-time workplace selection; it cannot change OD.
    for k,code in enumerate(codes):
        ids=np.flatnonzero(home_mun==code)
        if workers[k]:
            own=integer_totals(np.array([p['_employed'] for p in homes])[ids],workers[k])
            seed=np.outer(own,od[k]).astype(float)
            quotas[ids]=balanced_dense(seed,own,od[k])
        ids=np.flatnonzero(workmun==code)
        point_jobs[ids]=integer_totals(placement.weight.to_numpy()[ids],jobs[k])
    router=RoadRouter()
    haccess,_=router.snap([p['location'] for p in homes]);jaccess,_=router.snap([p['location'] for p in workplaces])
    pd.DataFrame({'id':[p['id'] for p in homes+workplaces],
        'road_connector_m':np.r_[haccess,jaccess],'over_1500m':np.r_[haccess,jaccess]>1500}).to_csv(reports/'road_access.csv',index=False)
    # Each destination caches travel to ALL homes; expanding sparse support needs
    # no repeated graph traversal. All paths follow directed road travel times.
    key=hashlib.sha256((digest(DATA/'geography.pkl')+digest(ROOT/'road_router.py')+
        json.dumps([p['location'] for p in homes+workplaces],separators=(',',':'))).encode()).hexdigest()[:24]
    cache=DATA/'quality_routes'/key;cache.mkdir(parents=True,exist_ok=True)
    routes=[];flow_rows=[];iterations=[]
    for k,code in enumerate(codes):
        origin_ids=np.flatnonzero(quotas[:,k]>0);destination_ids=np.flatnonzero((workmun==code)&(point_jobs>0))
        if not len(origin_ids):continue
        rt=quotas[origin_ids,k];ct=point_jobs[destination_ids]
        print(f'Routing {code}: {len(origin_ids)} homes, {len(destination_ids)} workplaces',flush=True)
        lengths=np.empty((len(origin_ids),len(destination_ids)),dtype=np.int32)
        seconds=np.empty_like(lengths)
        for j,d in enumerate(destination_ids):
            path=cache/(workplaces[d]['id']+'.npy')
            if path.exists():values=np.load(path)
            else:
                values=np.asarray(router.to_destination(workplaces[d]['location'],[p['location'] for p in homes],max_access_m=float('inf')),dtype=np.int32)
                temp=path.with_suffix('.tmp.npy');np.save(temp,values);temp.replace(path)
            lengths[:,j]=values[origin_ids,0];seconds[:,j]=values[origin_ids,1]
            if j%40==0:print(f'  {j+1}/{len(destination_ids)} routes cached',flush=True)
        # Nearest ROAD-TIME choices, strong employment centers, and reverse
        # support. Expand adaptively; complete support guarantees feasibility.
        width=min(config['within_od_nearest_workplaces'],len(ct))
        while True:
            support=np.zeros(seconds.shape,dtype=bool)
            nearest=np.argpartition(seconds,width-1,axis=1)[:,:width]
            support[np.arange(len(rt))[:,None],nearest]=True
            largest=np.argsort(-ct,kind='stable')[:config['within_od_largest_workplaces']]
            support[:,largest]=True
            reverse=min(max(config['within_od_nearest_origins_per_workplace'],width*2),len(rt))
            nearest_h=np.argpartition(seconds,reverse-1,axis=0)[:reverse,:]
            support[nearest_h,np.arange(len(ct))[None,:]]=True
            rr,cc=np.where(support)
            seed=ct[cc]*np.exp(-np.minimum(seconds[rr,cc]/config['gravity_decay_seconds'],50))
            try:
                fitted=fit_sparse(rr,cc,seed,rt,ct,iterations=3000,tolerance=1e-6)
                sizes=round_transport(rr,cc,fitted,rt,ct);break
            except ValueError:
                if width==len(ct):raise
                width=min(len(ct),max(width+1,width*2))
                print(f'  Expanding support to {width} destinations/home',flush=True)
        iterations.append({'municipality_code':code,'origins':len(rt),'workplaces':len(ct),'support_edges':len(rr),'nearest_road_destinations':width})
        for r,c,size in zip(rr,cc,sizes):
            if size==0:continue
            h=int(origin_ids[r]);d=int(destination_ids[c]);pid=str(len(routes))
            routes.append({'id':pid,'residenceId':homes[h]['id'],'jobId':workplaces[d]['id'],
                'size':int(size),'drivingDistance':int(lengths[r,c]),'drivingSeconds':int(seconds[r,c])})
            homes[h]['popIds'].append(pid);workplaces[d]['popIds'].append(pid);workplaces[d]['jobs']+=int(size)
            flow_rows.append((home_mun[h],code,int(size),int(lengths[r,c]),int(seconds[r,c])))
    for p in homes:p.pop('_employed',None)
    pd.DataFrame(iterations).to_csv(reports/'routing_support.csv',index=False)
    pd.DataFrame({'id':[p['id'] for p in homes],'commuters':quotas.sum(axis=1)}).to_csv(reports/'resident_commuters.csv',index=False)
    pd.DataFrame({'id':[p['id'] for p in workplaces],'target_jobs':point_jobs,
        'actual_jobs':[p['jobs'] for p in workplaces]}).to_csv(reports/'workplace_capacities.csv',index=False)
    flows=pd.DataFrame(flow_rows,columns=['origin','destination','size','distance_m','seconds'])
    flows.groupby(['origin','destination'])['size'].sum().rename('actual').to_csv(reports/'od_actual.csv')
    return {'points':homes+workplaces,'pops':routes},flows


def main(refresh_baseline=False):
    config=json.loads((ROOT/'quality_config.json').read_text())
    required=[DATA/'quality_prepared/cnefe_units.parquet',DATA/'quality_prepared/rais_postal_activity.parquet',
        DATA/'quality_sources/census2010/RJ.zip',DATA/'quality_sources/pnad/PNADC_022026.zip']
    if any(not p.exists() for p in required):
        subprocess.run([sys.executable,str(ROOT/'fetch_quality_sources.py')],check=True,cwd=ROOT)
        subprocess.run([sys.executable,str(ROOT/'prepare_quality_sources.py')],check=True,cwd=ROOT)
    reports=ROOT/'reports'/'quality';reports.mkdir(parents=True,exist_ok=True)
    baseline=DATA/'quality_baseline';baseline.mkdir(exist_ok=True)
    for src in [OUT/'demand_data.json',DATA/'demand_metadata.json',DATA/'population_audit.json',DATA/'employment_audit.json',ROOT/'employment_by_neighborhood.csv',ROOT/'employment_by_municipality.csv']:
        if src.exists() and (refresh_baseline or not (baseline/src.name).exists()):shutil.copyfile(src,baseline/src.name)
    # Freeze the source lineage before replacing output; never use a previous
    # release's worker-only residents as the population input.
    source=json.loads((baseline/'demand_data.json').read_text())
    metadata=json.loads((baseline/'demand_metadata.json').read_text())
    print('Selecting residential addresses',flush=True)
    homes,meta=residential_anchors(source['points'],metadata,reports)
    employed,municipality,informal,info=workers_pnad(homes,meta,reports)
    shares,pnad=informal_composition(reports)
    if abs(pnad['informality_microdata']-informal)>.015:raise ValueError('PNAD microdata disagree with published control')
    workplaces,placement,coverage=workplace_points(workplace_addresses(reports),homes,municipality,informal,shares,config,reports)
    codes=sorted(set(municipality));emp=np.array([employed[municipality==m].sum() for m in codes])
    jobweights=np.array([placement.loc[placement.municipality_code==m,'weight'].sum() for m in codes])
    if set(placement.municipality_code)-set(codes):raise ValueError('Workplace outside resident municipal coverage')
    workers,jobs,od=municipal_model(codes,emp,jobweights,coverage,config,reports)
    for p,w in zip(homes,employed):p['_employed']=int(w)
    demand,flows=fine_flows(homes,workplaces,municipality,placement,workers,jobs,codes,od,config,reports)
    from quality_validation import validate
    audit=validate(demand,flows,codes,emp,workers,jobs,od,municipality,placement,coverage,reports)
    audit.update(info,population=sum(p['residents'] for p in homes),commuters=int(workers.sum()),
        employed_pnad_calibrated=int(emp.sum()),maximum_jobs_at_one_point=max(p['jobs'] for p in workplaces),
        method='RAIS2024 CEP/activity+CNEFE; Census2022 containment/2010 OD prior; exact municipal and point margins; road-time gravity',
        configuration=config,metropolitan_informality_share=informal,pops=len(demand['pops']))
    # All invariants must pass before the playable output changes.
    temporary=OUT/'demand_data.quality.tmp';temporary.write_text(json.dumps(demand,separators=(',',':'),ensure_ascii=False));temporary.replace(OUT/'demand_data.json')
    newmeta=meta+[{'id':r.id,'municipality':r.municipality_code,'location_method':'CNEFE workplace / RAIS CEP activity aggregate','sectors':[]} for r in placement.itertuples()]
    (DATA/'demand_metadata.json').write_text(json.dumps(newmeta,separators=(',',':'),ensure_ascii=False))
    population=json.loads((baseline/'population_audit.json').read_text());population.update(commuters=int(workers.sum()),pops=len(demand['pops']),employment_points=len(workplaces),employment_calibration=audit['method'])
    (DATA/'population_audit.json').write_text(json.dumps(population,indent=2)+'\n')
    (DATA/'employment_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (reports/'summary.json').write_text(json.dumps(audit,indent=2)+'\n')
    tracked=[ROOT/f for f in ['quality_pipeline.py','quality_placement.py','quality_od.py','quality_pnad.py','quality_validation.py','quality_config.json','prepare_quality_sources.py','road_router.py']]
    manifest={'code_and_config_sha256':{p.name:digest(p) for p in tracked},
        'inputs_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [baseline/'demand_data.json',baseline/'demand_metadata.json',DATA/'census_allocation.csv',DATA/'quality_prepared/cnefe_units.parquet',DATA/'quality_prepared/rais_postal_activity.parquet']}}
    (reports/'reproducibility.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:audit[k] for k in ['population','commuters','employed_pnad_calibrated','maximum_jobs_at_one_point','pops']},indent=2),flush=True)


if __name__=='__main__':main()
