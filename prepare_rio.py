"""Expanded geography, deduplicated Overture houses and current layer names."""
import gc,gzip,json,pickle
from collections import defaultdict
import duckdb
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point,box,shape,mapping
from shapely.ops import transform
from shapely.strtree import STRtree
import geography as old
from map_settings import *


def configure():
    DATA.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    old.CACHE=DATA;old.OUT=OUT;old.BBOX=VISUAL_BBOX;old.CLIP=box(*VISUAL_BBOX)


def merge_extracts():
    path=DATA/'osm.pkl'
    if path.exists():return
    regional=DATA/'sudeste.osm.pbf'
    if regional.exists() and regional.stat().st_size>100000000:
        old.extract(regional)
        return
    nodes,ways,relations,labels=pickle.loads((ROOT/'data/osm_core.pkl').read_bytes())
    relation_keys={tuple(m) for m,_ in relations}
    for name in ['north','west','east','south']:
        data=json.loads(gzip.decompress((DATA/f'fringe_{name}.json.gz').read_bytes()))
        for e in data['elements']:
            tags=e.get('tags',{})
            if e['type']=='node':
                nodes[e['id']]=(e['lon'],e['lat'])
                if tags.get('place') and tags.get('name'):
                    place=tags['place'];layer='city_labels' if place in {'city','town'} else 'suburb_labels' if place in {'suburb','village'} else 'neighborhood_labels'
                    labels.append((layer,old.feature(Point(e['lon'],e['lat']),{'name':tags['name']})))
            elif e['type']=='way':ways[e['id']]=(e['nodes'],tags)
            elif e['type']=='relation' and tags.get('type') in {'multipolygon','boundary'}:
                members=[(m['ref'],m.get('role','')) for m in e['members'] if m['type']=='way']
                if tuple(members) not in relation_keys:
                    relations.append((members,tags));relation_keys.add(tuple(members))
        del data
    path.write_bytes(pickle.dumps((nodes,ways,relations,labels),protocol=5))
    print(f'Merged OSM: {len(nodes):,} nodes, {len(ways):,} ways',flush=True)


def geography():
    configure()
    if (DATA/'geography.pkl').exists():return
    merge_extracts()
    raw=pickle.loads((DATA/'osm.pkl').read_bytes())
    buildings,surfaces,labels,edges,nodes=old.geography(raw)
    del raw;gc.collect()
    # Preserve typed footprints and useful height metadata for conflation.
    rows=[]
    for f in buildings:
        props=f['properties'];g=shape(f['geometry'])
        rows.append((g,props['height'],props.get('height_known',False),props.get('use',''),props.get('name','')))
    pd.DataFrame(rows,columns=['geometry','height','height_known','use','name']).to_pickle(DATA/'osm_buildings.pkl')
    (DATA/'geography.pkl').write_bytes(pickle.dumps((surfaces,labels,edges,nodes),protocol=5))
    print('Expanded geography cached',flush=True)


def buildings():
    configure()
    if (DATA/'buildings.pkl').exists():return
    osm=pd.read_pickle(DATA/'osm_buildings.pkl')
    con=duckdb.connect()
    df=con.execute("SELECT * FROM read_parquet(?)",[str(DATA/'overture.parquet')]).fetchdf()
    con.close()
    print(f'Overture: {len(df):,} footprints; OSM: {len(osm):,}',flush=True)
    tree=STRtree(osm.geometry.to_numpy())
    used=set();result=[];clip=box(*VISUAL_BBOX)
    for row in df.itertuples(index=False):
        g=shapely.from_wkb(bytes(row.geometry))
        if not g.is_valid:g=shapely.make_valid(g)
        g=g.intersection(clip)
        for p in old.parts(g,'Polygon'):
            metric=transform(old.PROJECT,p)
            if metric.area<8:continue
            p=transform(old.UNPROJECT,metric.simplify(.12,preserve_topology=True))
            candidates=tree.query(p,predicate='intersects')
            match=None;best=0.
            for i in candidates:
                q=osm.geometry.iloc[i];inter=p.intersection(q).area
                score=inter/min(p.area,q.area) if min(p.area,q.area)>0 else 0
                if score>best:best=score;match=int(i)
            height=float(row.height) if pd.notna(row.height) and row.height>0 else None
            if height is None and pd.notna(row.num_floors) and row.num_floors>0:height=float(row.num_floors)*3
            known=height is not None
            use=str(row.subtype) if pd.notna(row.subtype) else 'residential'
            name=''
            if match is not None and best>.45:
                used.add(match)
                if bool(osm.height_known.iloc[match]):height=float(osm.height.iloc[match]);known=True
                if osm.use.iloc[match] not in {'yes','','no'}:use=osm.use.iloc[match]
                name=osm.name.iloc[match]
            # Missing height is an explicit low-rise estimate, not measured data.
            height=max(2.5,min(350,height if height is not None else 6.))
            result.append((p,height,known,use,name,'overture'))
    for i,row in enumerate(osm.itertuples(index=False)):
        if i not in used:
            result.append((row.geometry,row.height,row.height_known,row.use,row.name,'osm'))
    output=pd.DataFrame(result,columns=['geometry','height','height_known','use','name','source'])
    output.to_pickle(DATA/'buildings.pkl')
    print(f'Combined: {len(output):,} buildings',flush=True)


if __name__=='__main__':
    geography();buildings()
