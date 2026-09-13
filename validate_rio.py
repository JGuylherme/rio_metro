"""Independent output checks for the expanded census-based map."""
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,zipfile
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Point,box,shape
from shapely.strtree import STRtree
import mapbox_vector_tile
from pmtiles.reader import Reader,MmapSource,all_tiles
from binary_index import binary
from map_settings import *


def main():
    report={'version':VERSION,'playable_bbox':PLAY_BBOX,'visual_bbox':VISUAL_BBOX,'in_game_test':False}
    report['binary']=binary(OUT/'buildings_index.bin');print('SBBI validated',flush=True)
    config=json.loads((OUT/'config.json').read_text())
    assert config['code']=='RIO' and config['version']==VERSION
    d=json.loads((OUT/'demand_data.json').read_text());points={p['id']:p for p in d['points']}
    assert len(points)==len(d['points'])
    homes=Counter();jobs=Counter();members=defaultdict(set);seen=set()
    for p in d['pops']:
        assert p['id'] not in seen;seen.add(p['id'])
        assert p['residenceId'] in points and p['jobId'] in points
        assert all(isinstance(p[k],int) and p[k]>0 for k in ['size','drivingSeconds','drivingDistance'])
        homes[p['residenceId']]+=p['size'];jobs[p['jobId']]+=p['size']
        members[p['residenceId']].add(p['id']);members[p['jobId']].add(p['id'])
    play=box(*PLAY_BBOX)
    for pid,p in points.items():
        assert play.covers(Point(p['location']))
        assert p['residents']>=homes[pid] and p['jobs']==jobs[pid]
        assert len(p['popIds'])==len(set(p['popIds'])) and set(p['popIds'])==members[pid]
    audit=json.loads((DATA/'population_audit.json').read_text())
    assert sum(p['residents'] for p in points.values())==audit['population']==config['population']
    assert sum(homes.values())==sum(jobs.values())==audit['commuters']
    assert audit['neighborhood_totals_preserved']
    allocations=pd.read_csv(DATA/'census_allocation.csv')
    assert allocations.assigned_population.sum()==audit['population']
    neighborhoods=pd.read_csv(ROOT/'population_by_neighborhood.csv')
    assert neighborhoods.population.sum()==audit['population']
    assert neighborhoods[neighborhoods.municipality=='Japeri'].population.sum()>50000
    report['census']=audit;print('Census totals and commuter groups validated',flush=True)
    for name in ['roads.geojson','runways_taxiways.geojson']:
        feats=json.loads((OUT/name).read_text())['features']
        for f in feats:
            g=shape(f['geometry']);assert g.is_valid and not g.is_empty
            assert box(*VISUAL_BBOX).buffer(1e-7).covers(g)
        report[name]={'features':len(feats)}
    ocean=json.loads(gzip.decompress((OUT/'ocean_depth_index.json.gz').read_bytes()))
    assert ocean['bbox']==list(PLAY_BBOX)
    assert ocean['stats']['count']==len(ocean['depths'])>1000
    assert ocean['stats']['maxDepth']==0
    for e in ocean['depths']:
        assert np.isfinite(e['d']) and e['d']<0
        assert shape({'type':'Polygon','coordinates':e['p']}).is_valid
    for col,row,*refs in ocean['cells']:
        assert 0<=col<ocean['grid'][0] and 0<=row<ocean['grid'][1]
        assert refs and all(0<=r<len(ocean['depths']) for r in refs)
    report['water']=json.loads((DATA/'bathymetry_audit.json').read_text())
    report['tiles']={}
    for name in ['RIO.pmtiles','RIO_foundations.pmtiles']:
        with (OUT/name).open('rb') as f:
            source=MmapSource(f);reader=Reader(source);header=reader.header();counts=Counter();n=0;sampled_zooms=set()
            for (z,x,y),raw in all_tiles(source):
                payload=gzip.decompress(raw)
                from mapbox_vector_tile.Mapbox import vector_tile_pb2
                tile=vector_tile_pb2.tile();tile.ParseFromString(payload)
                for layer in tile.layers:
                    assert layer.extent>=4096 and layer.version in (1,2)
                    counts[layer.name]+=len(layer.features)
                    for q in layer.features:
                        assert q.type in (1,2,3) and q.geometry
                        tags=q.tags
                        assert len(tags)%2==0
                        assert all(tags[i]<len(layer.keys) and tags[i+1]<len(layer.values) for i in range(0,len(tags),2))
                    if layer.name in {'buildings','ocean_foundations'}:
                        key='height' if layer.name=='buildings' else 'depth_min'
                        assert key in layer.keys
                        key_index=list(layer.keys).index(key)
                        for q in layer.features:
                            ids=[q.tags[i+1] for i in range(0,len(q.tags),2) if q.tags[i]==key_index]
                            assert ids
                            v=layer.values[ids[0]]
                            value=next(value for descriptor,value in v.ListFields())
                            assert np.isfinite(value) and (value>0 if key=='height' else value<0)
                # Decode full geometry on a deterministic sample, including each zoom.
                if n%500==0 or z not in sampled_zooms:
                    mapbox_vector_tile.decode(payload);sampled_zooms.add(z)
                n+=1
                if n%2000==0:print(name,n,'tiles verified',flush=True)
            required={'buildings','water','parks','airports','commercial','scenery_roads'} if name=='RIO.pmtiles' else {'foundations','ocean_foundations'}
            assert required<=set(counts)
            assert header['max_zoom']==15 and n==header['addressed_tiles_count']
            report['tiles'][name]={'tiles':n,'features_by_layer':dict(counts),'validation':'all protobuf messages and feature properties; full geometry sampled every 500 tiles and each zoom'}
    buildings=pd.read_pickle(DATA/'buildings.pkl');tree=STRtree(buildings.geometry.to_numpy())
    windows={'Japeri':(-43.73,-22.69,-43.58,-22.59),'Zona Oeste':(-43.75,-22.96,-43.5,-22.83),
        'Complexo do Alemão':(-43.30,-22.88,-43.26,-22.84),'Rocinha':(-43.26,-23.00,-43.23,-22.97),
        'São Gonçalo':(-43.09,-22.87,-42.85,-22.75),'Sul de Niterói':(-43.09,-23.02,-42.95,-22.93)}
    report['building_coverage_samples']={name:{'sample_bbox':bounds,'buildings':len(tree.query(box(*bounds),predicate='intersects'))} for name,bounds in windows.items()}
    assert all(v['buildings']>100 for v in report['building_coverage_samples'].values())
    report['buildings']=json.loads((DATA/'building_audit.json').read_text())
    assert report['buildings']['visual_buildings']>317791
    from package_rio import FILES, main as package
    names=FILES
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    report['files']={name:{'bytes':(OUT/name).stat().st_size,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()} for name in names}
    package()
    # The released demand uses commuter counts; source demand retains census totals.
    with zipfile.ZipFile(dist/'RIO.zip') as archive:
        payload=archive.read('demand_data.json')
        released=json.loads(payload)
        assert sum(p['residents'] for p in released['points'])==sum(p['size'] for p in released['pops'])==audit['commuters']
        assert released['pops']==d['pops']
        report['files']['demand_data.json']={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    report['archive']={'path':'dist/RIO.zip','bytes':(dist/'RIO.zip').stat().st_size}
    (ROOT/'validation_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
