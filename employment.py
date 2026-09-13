"""Calibrate worker origins and job destinations using PNAD, CEMPRE and RAIS."""
import json
from collections import defaultdict
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree
from map_settings import ROOT,DATA,OUT


def integer_totals(values,total=None):
    values=np.asarray(values,float)
    total=round(values.sum()) if total is None else int(total)
    if total==0:return np.zeros(len(values),dtype=int)
    values=values*(total/values.sum())
    result=np.floor(values).astype(int)
    order=np.argsort(-(values-result),kind='stable')
    result[order[:total-result.sum()]]+=1
    return result


def benchmarks(points):
    from fetch_employment import main
    main()
    folder=DATA/'employment_sources'
    pn=json.loads((folder/'pnad_current.json').read_text())[1:]
    pop=json.loads((folder/'population_current.json').read_text())[1:]
    vals={(r['D1C'],r['D2C']):float(r['V']) for r in pn}
    totals={r['D1C']:float(r['V']) for r in pop}
    rates={'capital':vals['3304557','4090']/totals['3304557'],
        'metropolitan_remainder':(vals['3301','4090']-vals['3304557','4090'])/(totals['3301']-totals['3304557']),
        'state':vals['33','4090']/totals['33']}
    informal=vals['3301','12466']/100
    cempre={r['D1C']:float(r['V']) for r in json.loads((folder/'cempre_current.json').read_text())[1:] if r['D2C']=='707' and r['V'] not in ['-','...','X']}
    census=pd.read_pickle(DATA/'census.pkl')
    positions=shapely.points([p['location'] for p in points]);tree=STRtree(census.geometry.to_numpy())
    joins=tree.query(positions,predicate='intersects');sector=np.full(len(points),-1,dtype=int)
    for i,j in zip(*joins):sector[i]=j
    missing=np.flatnonzero(sector<0)
    if len(missing):sector[missing]=tree.nearest(positions[missing])
    mun=census.iloc[sector].CD_MUN.astype(str).to_numpy()
    municipality=census.iloc[sector].NM_MUN.to_numpy()
    bairro=census.iloc[sector].NM_BAIRRO.fillna('').to_numpy()
    # Exact neighborhood geometry from the RAIS geography, rather than name guesses.
    records=json.loads((folder/'rais_bairros_2023.geojson').read_text())['features']
    records=[r for r in records if r['geometry'] is not None]
    geoms=np.array([shape(r['geometry']) for r in records],dtype=object)
    bt=STRtree(geoms);bj=bt.query(positions,predicate='intersects')
    neighborhood=np.full(len(points),-1,dtype=int)
    for i,j in zip(*bj):
        if mun[i]=='3304557':neighborhood[i]=j
    missing_rio=np.flatnonzero((mun=='3304557') & (neighborhood<0))
    if len(missing_rio):neighborhood[missing_rio]=bt.nearest(positions[missing_rio])
    # Full-municipality populations make edge-of-map CEMPRE weights proportional.
    import pyogrio
    full=pyogrio.read_dataframe(DATA/'RJ_setores_CD2022.gpkg',columns=['CD_MUN','v0001'],read_geometry=False)
    fullpop=full.groupby('CD_MUN').v0001.sum().to_dict()
    residents=np.array([p['residents'] for p in points])
    metropolitan={'3300456','3301702','3301850','3301900','3302007','3302270','3302502','3302700','3302858','3303203','3303302','3303500','3303609','3304144','3304557','3304904','3305109','3305554'}
    worker_rates=np.array([rates['capital'] if m=='3304557' else rates['metropolitan_remainder'] if m in metropolitan else rates['state'] for m in mun])
    workers=integer_totals(residents*worker_rates)
    keys=[];labels={}
    for i,p in enumerate(points):
        if neighborhood[i]>=0:
            props=records[neighborhood[i]]['properties'];key=(mun[i],props['nome']);bairro[i]=props['nome']
        else:key=(mun[i],'Total no recorte municipal')
        keys.append(key);labels[key]=(str(municipality[i]),key[1])
    unique=sorted(set(keys));lookup={k:i for i,k in enumerate(unique)};groups=np.array([lookup[k] for k in keys])
    group_pop=np.bincount(groups,weights=residents,minlength=len(unique))
    formal=np.zeros(len(unique));group_kind=np.zeros(len(unique))
    # Within municipalities without neighborhood RAIS, mapped job sites plus local services are proxies.
    for i,p in enumerate(points):group_kind[groups[i]]+=max(1,p['residents']*.03) if p['residents'] else 500 if p['id'].startswith('IND') else 200
    municipality_weights={}
    for m in sorted(set(mun)):
        ids=np.flatnonzero(mun==m);coverage=min(1,residents[ids].sum()/float(fullpop.get(m,1)))
        municipality_weights[m]=cempre.get(m,0)*coverage
        gs=sorted(set(groups[ids]));weights=[]
        for g in gs:
            key=unique[g]
            if m=='3304557':
                records_for_name=[r for r in records if r['properties']['nome']==key[1]]
                weights.append(sum(r['properties']['vinculos'] or 0 for r in records_for_name))
            else:weights.append(group_kind[g])
        if sum(weights)==0:weights=[group_pop[g] for g in gs]
        formal[gs]=np.asarray(weights)/sum(weights)*municipality_weights[m]
    total_workers=int(workers.sum())
    formal_component=formal/formal.sum()*(1-informal)*total_workers
    # Informality is not geocoded in RAIS. Explicit mixed proxy, not observed neighborhood totals.
    informal_weights=.75*group_pop/group_pop.sum()+.25*formal/formal.sum()
    informal_component=informal_weights*informal*total_workers
    targets=integer_totals(formal_component+informal_component,total_workers)
    rows=[{'group':g,'municipality_code':key[0],'municipality':labels[key][0],'bairro':labels[key][1],
        'residents':int(group_pop[g]),'target_jobs':int(targets[g]),
        'rais_2023_formal_links':sum(r['properties']['vinculos'] or 0 for r in records if r['properties']['nome']==key[1]) if key[0]=='3304557' else None,
        'cempre_2024_municipality_persons':cempre.get(key[0]),'formal_component_estimated':round(formal_component[g],2),
        'informal_component_estimated':round(informal_component[g],2),'spatial_source':'RAIS 2023 neighborhood shares + CEMPRE 2024' if key[0]=='3304557' else 'CEMPRE 2024 municipality + mapped employment/local services proxy'} for g,key in enumerate(unique)]
    pd.DataFrame(rows).to_csv(ROOT/'employment_by_neighborhood.csv',index=False)
    point_rows=[{'id':p['id'],'municipality':str(municipality[i]),'bairro':str(bairro[i]),'group':int(groups[i]),'worker_rate':float(worker_rates[i])} for i,p in enumerate(points)]
    (DATA/'employment_locations.json').write_text(json.dumps(point_rows,ensure_ascii=False,separators=(',',':')))
    info={'pnad_period':'2026Q2','cempre_year':2024,'rais_neighborhood_year':2023,'rates_occupied_over_total_population':rates,
        'metropolitan_unemployment_rate':vals['3301','4099']/100,'metropolitan_informality_share':informal,
        'informal_spatial_proxy':'75% resident population + 25% formal employment geography',
        'geographic_nearest_fallbacks':int(len(missing)),'rio_neighborhood_nearest_fallbacks':int(len(missing_rio)),
        'municipality_formal_weights':municipality_weights,'counts_are_calibrated_estimates_not_official_neighborhood_job_totals':True}
    return workers,groups,targets,info


def rebalance(demand):
    points=demand['points'];routes=demand['pops'];index={p['id']:i for i,p in enumerate(points)}
    workers,groups,targets,info=benchmarks(points)
    from employment_routes import expand
    routes=expand(points,routes,workers,groups,targets)
    origin=np.array([index[p['residenceId']] for p in routes]);dest=np.array([index[p['jobId']] for p in routes])
    dest_group=groups[dest];before=np.array([p['jobs'] for p in points])
    # Allocate by neighborhood; old, erroneous simulated job counts are never weights.
    attraction=np.array([max(10,p['residents']*.03) if p['residents'] else 500 if p['id'].startswith('IND') else 200 for p in points])
    values=attraction[dest]*np.exp(-np.array([p['drivingSeconds'] for p in routes])/2400)
    group_supply=np.bincount(dest_group,weights=values,minlength=len(targets))
    unavailable=np.flatnonzero((targets>0)&(group_supply==0))
    if len(unavailable):raise RuntimeError('Neighborhoods without routes: '+str(unavailable.tolist()))
    # A demand marker aggregates nearby workplaces; guard against single-site spikes.
    point_capacity=np.full(len(points),20000.,dtype=float)
    for g,target in enumerate(targets):
        supported=np.unique(dest[dest_group==g])
        if len(supported):point_capacity[supported]=max(20000.,np.ceil(target/len(supported))+10)
    for iteration in range(10000):
        rows=np.bincount(origin,weights=values,minlength=len(points))
        if np.any((workers>0)&(rows==0)):raise RuntimeError('Residential origin without routes')
        values*=np.divide(workers,rows,out=np.zeros(len(points)),where=rows>0)[origin]
        cols=np.bincount(dest_group,weights=values,minlength=len(targets))
        error=float(np.max(np.abs(cols-targets)))
        point_totals=np.bincount(dest,weights=values,minlength=len(points))
        excess=float(np.max(point_totals-point_capacity+5))
        if error<.01 and excess<.001:break
        values*=np.divide(targets,cols,out=np.zeros(len(targets)),where=cols>0)[dest_group]
        point_totals=np.bincount(dest,weights=values,minlength=len(points))
        values*=np.minimum(1,np.divide(point_capacity-5,point_totals,out=np.ones(len(points)),where=point_totals>0))[dest]
        if iteration%1000==0:print('Employment balancing',iteration,'max neighborhood residual',round(error,2),flush=True)
    else:raise RuntimeError('Existing routes cannot meet neighborhood targets; regeneration needed')
    # Round each residence exactly; publish neighborhood rounding residuals.
    sizes=np.floor(values).astype(int)
    by_origin=defaultdict(list)
    for k,i in enumerate(origin):by_origin[int(i)].append(k)
    for i,ids in by_origin.items():
        remaining=int(workers[i]-sizes[ids].sum());order=sorted(ids,key=lambda k:values[k]-sizes[k],reverse=True)
        if remaining<0 or remaining>len(ids):raise RuntimeError('Rounding mismatch')
        sizes[order[:remaining]]+=1
    for p in points:p['jobs']=0;p['popIds']=[]
    output=[]
    for route,size in zip(routes,sizes):
        if not size:continue
        p={**route,'id':str(len(output)),'size':int(size)};output.append(p)
        home=points[index[p['residenceId']]];job=points[index[p['jobId']]]
        home['popIds'].append(p['id']);job['popIds'].append(p['id']);job['jobs']+=int(size)
    demand['pops']=output
    actual=np.array([p['jobs'] for p in points]);actual_group=np.bincount(groups,weights=actual,minlength=len(targets)).astype(int)
    df=pd.read_csv(ROOT/'employment_by_neighborhood.csv');df['jobs']=actual_group;df['rounding_difference']=actual_group-targets
    df['resident_workers']=np.bincount(groups,weights=workers,minlength=len(targets)).astype(int)
    df.to_csv(ROOT/'employment_by_neighborhood.csv',index=False)
    df.groupby('municipality')[['residents','resident_workers','jobs']].sum().to_csv(ROOT/'employment_by_municipality.csv')
    locations=json.loads((DATA/'employment_locations.json').read_text())
    fundao=np.array([x['municipality']=='Rio de Janeiro' and x['bairro']=='Cidade Universitária' for x in locations])
    info.update({'method':'doubly constrained gravity model on existing road routes; PNAD residence totals and CEMPRE/RAIS job geography',
        'population':sum(p['residents'] for p in points),'commuters':int(actual.sum()),'fundao_jobs_before':int(before[fundao].sum()),
        'fundao_jobs_after':int(actual[fundao].sum()),'fundao_definition':'RAIS Cidade Universitária neighborhood polygon, excluding mainland neighbors','maximum_jobs_at_one_point':int(actual.max()),'iterations':iteration+1,
        'pops':len(output),'max_neighborhood_rounding_difference':int(np.abs(actual_group-targets).max())})
    (DATA/'employment_audit.json').write_text(json.dumps(info,indent=2,ensure_ascii=False)+'\n')
    return demand


def main():
    path=OUT/'demand_data.json'
    demand=rebalance(json.loads(path.read_text()))
    path.write_text(json.dumps(demand,separators=(',',':'),ensure_ascii=False))
    audit=json.loads((DATA/'population_audit.json').read_text());audit['pops']=len(demand['pops'])
    audit['commuters']=sum(p['size'] for p in demand['pops']);audit.pop('commuter_share_assumption',None)
    audit['employment_calibration']='PNAD 2026Q2 / CEMPRE 2024 / RAIS neighborhoods 2023'
    (DATA/'population_audit.json').write_text(json.dumps(audit,separators=(',',':')))
    print((DATA/'employment_audit.json').read_text(),flush=True)

if __name__=='__main__':main()
