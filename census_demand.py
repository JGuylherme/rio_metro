"""Census-constrained residents and land-use-based employment for Rio."""
from collections import Counter,defaultdict
import csv,json,math,pickle
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point,box,shape
from shapely.ops import unary_union,transform
from shapely.strtree import STRtree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components,dijkstra
from scipy.spatial import cKDTree
import geography as util
from map_settings import *


def text(v,default=''):
    return str(v) if pd.notna(v) and str(v).strip() not in {'','.'} else default


def unique_census(census):
    """Multipart source records repeat tract attributes; count each tract once."""
    for _, rows in census.groupby('CD_SETOR'):
        if rows.v0001.nunique(dropna=False) != 1 or rows.CD_MUN.nunique() != 1:
            raise ValueError('Conflicting attributes for a repeated census sector')
    return census.dissolve(by='CD_SETOR',aggfunc='first').reset_index()


def generate():
    if (OUT/'demand_data.json').exists() and (DATA/'population_audit.json').exists():return
    buildings=pd.read_pickle(DATA/'buildings.pkl')
    census=unique_census(pd.read_pickle(DATA/'census.pkl'))
    surfaces,labels,edges,nodes=pickle.loads((DATA/'geography.pkl').read_bytes())
    play=box(*PLAY_BBOX)
    water=unary_union([shape(f['geometry']) for layer,f in surfaces if layer=='water'])
    forest=unary_union([shape(f['geometry']) for layer,f in surfaces if layer=='landuse' and f['properties'].get('kind')=='park'])
    industrial=unary_union([shape(f['geometry']) for layer,f in surfaces if layer=='industrial'])
    # Reuse polygon indexes for millions of point tests instead of scanning rings.
    for geometry in (play,water,forest,industrial):shapely.prepare(geometry)
    print('Census geometry prepared; locating building anchors',flush=True)
    geoms=buildings.geometry.to_numpy()
    anchors=shapely.point_on_surface(geoms)
    inside=shapely.covers(play,anchors)
    wet=shapely.covers(water,anchors)
    wooded=shapely.covers(forest,anchors)
    industry=shapely.covers(industrial,anchors)
    nonres={'industrial','warehouse','commercial','retail','school','university','hospital','service','garage','garages','farm_auxiliary','shed','parking','manufacturing','agricultural'}
    residential=~buildings['use'].isin(nonres).to_numpy() & ~wet & ~industry
    explicit=buildings['use'].isin({'house','apartments','residential','detached','terrace','semidetached_house'}).to_numpy()
    # Sector joins keep residents in their actual census neighborhood.
    sector_tree=STRtree(census.geometry.to_numpy())
    matches=sector_tree.query(anchors,predicate='within')
    members=defaultdict(list)
    for building_id,sector_id in zip(*matches):members[int(sector_id)].append(int(building_id))
    square_meters_per_square_degree=111132**2*math.cos(math.radians(-22.85))
    weights=np.maximum(8,shapely.area(geoms)*square_meters_per_square_degree)*np.minimum(buildings.height.to_numpy()/3,8)
    clusters=defaultdict(list);unplaced=[];sector_audit=[];expected=Counter()
    for i,row in census.iterrows():
        pop=int(row.v0001)
        if pop<=0:continue
        group=text(row.CD_BAIRRO,text(row.CD_SUBDIST,text(row.CD_MUN)))
        bairro=text(row.NM_BAIRRO,text(row.NM_SUBDIST,text(row.NM_MUN)))
        community=text(row.NM_FCU)
        all_ids=np.asarray(members.get(i,[]),dtype=int)
        suitable=all_ids[residential[all_ids] & (~wooded[all_ids] | explicit[all_ids] | bool(community))]
        eligible=suitable[inside[suitable]]
        sector=row.geometry
        clipped=sector.intersection(play)
        if clipped.is_empty:continue
        fraction=1.
        if not play.covers(sector):
            if len(suitable):fraction=len(eligible)/len(suitable)
            else:fraction=clipped.area/sector.area
        assigned=round(pop*fraction)
        if assigned<=0:continue
        expected[group]+=assigned
        method='building_in_census_sector'
        if len(eligible):
            xs=shapely.get_x(anchors[eligible]);ys=shapely.get_y(anchors[eligible]);w=weights[eligible]
            cx,cy=np.average(xs,weights=w),np.average(ys,weights=w)
            choice=eligible[np.argmin(((xs-cx)*.92)**2+(ys-cy)**2)]
            p=anchors[choice]
        else:
            # Only populated census polygons qualify, never arbitrary road cells.
            allowed=clipped.difference(water).difference(industrial)
            if not community:allowed=allowed.difference(forest)
            if allowed.is_empty:
                unplaced.append((group,assigned,bairro,text(row.NM_MUN),community,row.CD_SETOR));continue
            p=allowed.representative_point();method='populated_census_polygon'
        x,y=util.PROJECT(p.x,p.y)
        key=(group,community,int(x//800),int(y//800))
        clusters[key].append({'location':[p.x,p.y],'population':assigned,'bairro':bairro,
            'municipality':text(row.NM_MUN),'community':community,'sector':row.CD_SETOR,'method':method})
        sector_audit.append({'sector':row.CD_SETOR,'group':group,'census_population':pop,'assigned_population':assigned,'boundary_fraction':fraction})
    by_group=defaultdict(list)
    for key in clusters:by_group[key[0]].append(key)
    for group,pop,bairro,municipality,community,sector in unplaced:
        if not by_group[group]:raise RuntimeError(f'No residential location in census neighborhood {municipality}/{bairro}; cannot silently discard {pop} people')
        key=max(by_group[group],key=lambda k:sum(x['population'] for x in clusters[k]))
        first=clusters[key][0]
        clusters[key].append({**first,'population':pop,'sector':sector,'method':'same_neighborhood_occupied_location'})
        sector_audit.append({'sector':sector,'group':group,'census_population':pop,'assigned_population':pop,'boundary_fraction':1.})
    points=[];metadata=[];job_weights=[]
    for key,items in sorted(clusters.items()):
        # Use one actual residential anchor rather than averaging onto empty land.
        center=np.average([p['location'] for p in items],axis=0,weights=[p['population'] for p in items])
        chosen=min(items,key=lambda p:math.dist(p['location'],center))
        count=sum(p['population'] for p in items);pid=f'RES_{len(points):04d}'
        points.append({'id':pid,'location':chosen['location'],'residents':count,'jobs':0,'popIds':[]})
        metadata.append({'id':pid,'group':key[0],'kind':'residential','population':count,
            'bairro':chosen['bairro'],'municipality':chosen['municipality'],'community':key[1],
            'sectors':[p['sector'] for p in items],'location_method':chosen['method']})
        job_weights.append(count*.035)  # Neighborhood services; explicitly modeled.
    nres=len(points)
    print(f'Census allocated to {nres:,} residential points',flush=True)
    building_tree=STRtree(geoms)
    for kind,density in [('industrial',.022),('commercial',.065)]:
        polys=unary_union([shape(f['geometry']) for layer,f in surfaces if layer==kind]).intersection(play).difference(water)
        for poly in util.parts(polys,'Polygon'):
            metric_area=transform(util.PROJECT,poly).area
            if metric_area<250:continue
            ids=building_tree.query(poly,predicate='intersects')
            eligible=[i for i in ids if poly.covers(anchors[i]) and not wet[i]]
            if eligible:
                selected=max(eligible,key=lambda i:geoms[i].area)
                p=anchors[selected]
                floor_area=sum(transform(util.PROJECT,geoms[i]).area*min(buildings.height.iloc[i]/3,12) for i in eligible)
            else:p=poly.representative_point();floor_area=metric_area*.20
            if forest.covers(p):continue
            pid=f'{"IND" if kind=="industrial" else "COM"}_{len(points):04d}'
            points.append({'id':pid,'location':[p.x,p.y],'residents':0,'jobs':0,'popIds':[]})
            job_weights.append(max(5,floor_area*density))
            metadata.append({'id':pid,'kind':kind,'population':0,'location_method':'mapped_employment_landuse'})
    actual=Counter()
    for m in metadata:
        if m['kind']=='residential':actual[m['group']]+=m['population']
    assert actual==expected
    total_population=sum(actual.values())
    print(f'{total_population:,} census residents; {len(points)-nres:,} mapped employment centers',flush=True)
    # Employment calibration needs the current sector-to-anchor lineage.
    util.save(DATA/'demand_metadata.json',metadata)
    pd.DataFrame(sector_audit).to_csv(DATA/'census_allocation.csv',index=False)
    # Road network: actual directed shortest paths; no straight-line car routes.
    ids=sorted({e[0] for e in edges}|{e[1] for e in edges});idx={n:i for i,n in enumerate(ids)}
    pairs={}
    for a,b,length,secs,direction in edges:
        arcs=[(b,a)] if direction=='-1' else [(a,b)] if direction in {'yes','1','true'} else [(a,b),(b,a)]
        for a,b in arcs:
            key=(idx[a],idx[b])
            if key not in pairs or secs<pairs[key]:pairs[key]=secs
    rows,cols=zip(*pairs)
    graph=coo_matrix((list(pairs.values()),(rows,cols)),shape=(len(ids),len(ids))).tocsr()
    _,components=connected_components(graph,directed=True,connection='strong')
    keep=np.flatnonzero(components==np.bincount(components).argmax());graph=graph[keep][:,keep]
    positions=np.array([nodes[ids[i]] for i in keep]);xy=np.column_stack(util.PROJECT(positions[:,0],positions[:,1]))
    locations=np.array([p['location'] for p in points]);pxy=np.column_stack(util.PROJECT(locations[:,0],locations[:,1]))
    access,snap=cKDTree(xy).query(pxy)
    rng=np.random.default_rng(20260911);pops=[]
    from employment import benchmarks
    workers=benchmarks(points)[0][:nres]
    weights=np.asarray(job_weights)
    for start in range(0,nres,16):
        times,pred=dijkstra(graph,directed=True,indices=snap[start:start+16],return_predecessors=True)
        for local,origin in enumerate(range(start,min(start+16,nres))):
            t=times[local,snap];prob=weights*np.exp(-t/2400);prob[origin]=0;prob[~np.isfinite(t)]=0
            if not prob.sum():raise RuntimeError('No reachable jobs')
            dests=rng.choice(len(points),min(16,np.count_nonzero(prob)),replace=False,p=prob/prob.sum())
            sizes=rng.multinomial(int(workers[origin]),prob[dests]/prob[dests].sum())
            for dest,size in zip(dests,sizes):
                if not size:continue
                cursor=int(snap[dest]);length=0.
                while cursor!=snap[origin]:
                    previous=int(pred[local,cursor])
                    if previous<0:raise RuntimeError('Broken driving route')
                    length+=math.dist(xy[cursor],xy[previous]);cursor=previous
                pid=str(len(pops))
                pops.append({'id':pid,'residenceId':points[origin]['id'],'jobId':points[dest]['id'],'size':int(size),
                    'drivingDistance':max(1,round(length)), 'drivingSeconds':max(1,round(t[dest]))})
                points[origin]['popIds'].append(pid);points[dest]['popIds'].append(pid);points[dest]['jobs']+=int(size)
        if start%128==0:print(f'Routed {min(start+16,nres)}/{nres} residential points',flush=True)
    from employment import rebalance
    corrected=rebalance({'points':points,'pops':pops})
    pops=corrected['pops']
    util.save(OUT/'demand_data.json',corrected)
    util.save(DATA/'demand_metadata.json',metadata)
    pd.DataFrame(sector_audit).to_csv(DATA/'census_allocation.csv',index=False)
    pd.DataFrame([m for m in metadata if m['kind']=='residential']).groupby(['municipality','bairro'],dropna=False)['population'].sum().to_csv(ROOT/'population_by_neighborhood.csv')
    util.save(DATA/'population_audit.json',{'source':'IBGE Censo 2022, definitive census-sector geography with attributes',
        'population':total_population,'commuters':sum(p['size'] for p in pops),'employment_calibration':'Census 2022 age and municipal workers / PNAD informality / CEMPRE 2024 / RAIS 2023',
        'residential_points':nres,'employment_points':len(points)-nres,'pops':len(pops),
        'same_neighborhood_relocations':len(unplaced),'neighborhood_totals_preserved':actual==expected,
        'road_access_over_1000m':int((access>1000).sum()),'max_road_access_m':float(access.max()),
        'partial_boundary_sectors':sum(x['boundary_fraction']<1 for x in sector_audit)})


if __name__=='__main__':generate()
