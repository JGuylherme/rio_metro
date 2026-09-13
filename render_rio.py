"""Native tiles, detailed footprints, sea-level water and bathymetric collisions."""
import gzip,json,math,pickle,subprocess,types
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import box,shape,mapping
from shapely.ops import transform,unary_union
from shapely.prepared import prep
import geography as util
from map_settings import *


def foundation(g,height):
    metric=transform(util.PROJECT,g)
    rect=metric.minimum_rotated_rectangle
    coords=list(rect.exterior.coords)
    width=min(math.dist(coords[0],coords[1]),math.dist(coords[1],coords[2]))
    return int(max(10,min(80,.25*height*(height/max(width,.5))**.25)))


def bathymetry(surfaces,force=False):
    target=DATA/'bathymetry_features.pkl'
    if not force and target.exists() and (OUT/'ocean_depth_index.json.gz').exists():return pickle.loads(target.read_bytes())
    water=unary_union([shape(f['geometry']) for layer,f in surfaces if layer=='water'])
    ready=prep(water)
    ds=xr.open_dataset(DATA/'gmrt.nc');nx,ny=ds.dimension.values
    z=ds.z.values.reshape(ny,nx);west,east=ds.x_range.values;south,north=ds.y_range.values
    sx,sy=ds.spacing.values
    cs=.0027;stepx=cs/math.cos(math.radians((VISUAL_BBOX[1]+VISUAL_BBOX[3])/2))
    cols=math.ceil((VISUAL_BBOX[2]-VISUAL_BBOX[0])/stepx);rows=math.ceil((VISUAL_BBOX[3]-VISUAL_BBOX[1])/cs)
    features=[];fallback=0
    for col in range(cols):
        x=VISUAL_BBOX[0]+col*stepx
        column=water.intersection(box(x,VISUAL_BBOX[1],min(x+stepx,VISUAL_BBOX[2]),VISUAL_BBOX[3]))
        column_ready=prep(column)
        for row in range(rows):
            y=VISUAL_BBOX[1]+row*cs
            cell=box(x,y,min(x+stepx,VISUAL_BBOX[2]),min(y+cs,VISUAL_BBOX[3]))
            if not column_ready.intersects(cell):continue
            g=column.intersection(cell)
            p=g.representative_point();ix=int(np.clip(round((p.x-west)/sx),0,nx-1));iy=int(np.clip(round((north-p.y)/sy),0,ny-1))
            value=float(z[iy,ix])
            if not np.isfinite(value) or value>=-1:value=-2.;fallback+=1
            depth=round(value,1)
            for poly in util.parts(g,'Polygon'):
                if poly.area<1e-12:continue
                features.append(util.feature(poly,{'kind':'ocean_foundation','depth_min':depth}))
        if col%100==0:print(f'Bathymetry columns {col}/{cols}',flush=True)
    # Re-grid only the playable region for collision detection.
    play=box(*PLAY_BBOX);cs=.0027;stepx=cs/math.cos(math.radians((PLAY_BBOX[1]+PLAY_BBOX[3])/2))
    cols=math.ceil((PLAY_BBOX[2]-PLAY_BBOX[0])/stepx);rows=math.ceil((PLAY_BBOX[3]-PLAY_BBOX[1])/cs)
    from shapely.strtree import STRtree
    geoms=[shape(f['geometry']) for f in features];tree=STRtree(geoms);entries=[];cells=[]
    for col in range(cols):
        for row in range(rows):
            x=PLAY_BBOX[0]+col*stepx;y=PLAY_BBOX[1]+row*cs
            cell=box(x,y,min(x+stepx,PLAY_BBOX[2]),min(y+cs,PLAY_BBOX[3]));refs=[]
            for i in tree.query(cell,predicate='intersects'):
                for p in util.parts(geoms[i].intersection(cell),'Polygon'):
                    if p.area<1e-12:continue
                    refs.append(len(entries));entries.append({'b':list(p.bounds),'d':features[i]['properties']['depth_min'],'p':mapping(p)['coordinates']})
            if refs:cells.append([col,row,*refs])
    index={'cs':cs,'bbox':PLAY_BBOX,'grid':[cols,rows],'cells':cells,'depths':entries,
        'stats':{'count':len(entries),'minDepth':min(d['d'] for d in entries),'maxDepth':0}}
    temporary=OUT/'ocean_depth_index.json.gz.tmp'
    with gzip.open(temporary,'wt',encoding='utf8') as f:json.dump(index,f,separators=(',',':'))
    temporary.replace(OUT/'ocean_depth_index.json.gz')
    target.write_bytes(pickle.dumps(features,protocol=5))
    util.save(DATA/'bathymetry_audit.json',{'source':'GMRT GridServer','grid_size':[int(nx),int(ny)],
        'source_spacing_degrees':[float(sx),float(sy)],'sea_surface_m':0,
        'coastal_fallback_cells':fallback,'fallback_depth_m':-2,'collision_entries':len(entries)})
    return features


def write_feature(file,f,layer,minzoom=6):
    file.write(json.dumps({**f,'tippecanoe':{'layer':layer,'minzoom':minzoom,'maxzoom':15}},ensure_ascii=False,separators=(',',':'))+'\n')


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    buildings=pd.read_pickle(DATA/'buildings.pkl')
    surfaces,labels,edges,nodes=pickle.loads((DATA/'geography.pkl').read_bytes())
    del edges,nodes
    from repair_surfaces import stream_features,write_layers
    raw=pickle.loads((DATA/'osm.pkl').read_bytes())
    waterways,river_areas,coast=stream_features(raw);del raw
    surfaces=surfaces+river_areas
    ocean=bathymetry(surfaces,force=True)
    (DATA/'render_surfaces.pkl').write_bytes(pickle.dumps(surfaces,protocol=5))
    play=box(*PLAY_BBOX)
    base_path=DATA/'base.jsonl';found_path=DATA/'foundations.jsonl';index_path=DATA/'buildings_cleaned.json'
    with base_path.open('w') as base,found_path.open('w') as found,index_path.open('w') as index:
        index.write('{"type":"FeatureCollection","features":[');first=True;indexed=0
        for i,row in enumerate(buildings.itertuples(index=False)):
            props={'id':i+1,'kind':'building','height':float(row.height),'render_height':float(row.height),'min_height':0,'render_min_height':0,'sort_rank':400}
            f=util.feature(row.geometry,props);f['id']=i+1
            write_feature(base,f,'buildings',11)
            if play.intersects(row.geometry):
                for p in util.parts(row.geometry.intersection(play),'Polygon'):
                    if transform(util.PROJECT,p).area<8:continue
                    depth=foundation(p,row.height)
                    ff=util.feature(p,{'foundationDepth':depth});ff['id']=i+1
                    write_feature(found,ff,'foundations',12)
                    if not first:index.write(',')
                    index.write(json.dumps(util.feature(p,{'height':float(row.height)}),separators=(',',':')))
                    first=False;indexed+=1
            if i%100000==0:print(f'Writing detailed buildings {i}/{len(buildings)}',flush=True)
        index.write(']}')
        surface_path=DATA/'surface_layers.jsonl'
        write_layers(surface_path,surfaces,waterways,coast,ocean)
        with surface_path.open() as source:
            for line in source:base.write(line)
        seen=set()
        for layer,f in labels:
            key=(layer,f['properties'].get('name'),str(f['geometry']))
            if key not in seen and box(*VISUAL_BBOX).covers(shape(f['geometry'])):
                write_feature(base,f,layer,6 if layer=='city_labels' else 9 if layer=='suburb_labels' else 11);seen.add(key)
        roads_source=DATA/'visual_roads.geojson'
        roads=json.loads((roads_source if roads_source.exists() else OUT/'roads.geojson').read_text())['features'];interactive=[]
        if not roads_source.exists():util.save(roads_source,util.collection(roads))
        for f in roads:
            g=shape(f['geometry'])
            for p in util.parts(g.difference(play),'LineString'):
                write_feature(base,util.feature(p,f['properties']),'scenery_roads',6)
            for p in util.parts(g.intersection(play),'LineString'):interactive.append(util.feature(p,f['properties']))
        util.save(OUT/'roads.geojson',util.collection(interactive))
        for f in ocean:write_feature(found,f,'ocean_foundations',8)
    util.save(DATA/'building_audit.json',{'visual_buildings':len(buildings),'interactive_buildings':indexed,
        'measured_or_tagged_heights':int(buildings.height_known.sum()),'estimated_heights':int((~buildings.height_known).sum()),'minimum_area_m2':8})
    from depot.maps import MapGen
    generator=object.__new__(MapGen);generator._city='RIO';generator.verb=True;generator.create_building_foundations=True
    generator._calculate_building_foundation=types.MethodType(lambda self,coords,height:foundation(shape({'type':'Polygon','coordinates':[coords]}),height),generator)
    generator.create_buildings_index_binary(str(index_path))
    (OUT/'buildings_index.bin').write_bytes((DATA/'buildings_index.bin').read_bytes())
    import os
    env={**os.environ,'TIPPECANOE_MAX_THREADS':'4'}
    for source,destination in [(base_path,OUT/'RIO.pmtiles'),(found_path,OUT/'RIO_foundations.pmtiles')]:
        cmd=['tippecanoe','-o',str(destination),'-Z6','-z15','-r1','--force','--read-parallel',
            '--no-feature-limit','--no-tile-size-limit','--no-tiny-polygon-reduction-at-maximum-zoom',
            '--full-detail=14','--low-detail=12','--simplify-only-low-zooms','--buffer=4',
            '--clip-bounding-box='+','.join(map(str,VISUAL_BBOX)),
            '--name=Rio de Janeiro','--attribution=© OpenStreetMap contributors, Overture Maps Foundation; IBGE Censo 2022; GMRT',str(source)]
        print('Building',destination.name,'with native tile encoder',flush=True)
        subprocess.run(cmd,check=True,env=env)
    print('Detailed tiles and water depth index ready',flush=True)


if __name__=='__main__':run()
