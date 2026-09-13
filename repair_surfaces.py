"""Rebuild water/green layers and patch the map without regenerating buildings."""
import gzip,json,pickle,subprocess,os,heapq
from collections import Counter
from pathlib import Path
import shapely
from shapely.geometry import LineString,box,shape
from shapely.ops import transform,unary_union
from pmtiles.reader import Reader,MmapSource,all_tiles
from pmtiles.writer import Writer
from pmtiles.tile import zxy_to_tileid
from mapbox_vector_tile.Mapbox import vector_tile_pb2
import geography as util
from map_settings import DATA,OUT,VISUAL_BBOX,ROOT


def stream_features(raw):
    nodes,ways,_,_=raw;clip=box(*VISUAL_BBOX);waterways=[];water=[];coast=[]
    from fetch_waterways import main as fetch
    fetch()
    extra=json.loads((DATA/'waterways_osm.json').read_text())
    for element in extra['elements']:
        if element['type']!='way':continue
        refs=element.get('nodes',[]);coords=element.get('geometry',[])
        if len(refs)!=len(coords):continue
        for ref,p in zip(refs,coords):
            if 'lon' in p and 'lat' in p:nodes[ref]=(p['lon'],p['lat'])
        ways[element['id']]=(refs,element.get('tags',{}))
    for refs,tags in ways.values():
        kind=tags.get('waterway');is_coast=tags.get('natural')=='coastline'
        if not is_coast and kind not in {'river','stream','canal','drain','ditch'}:continue
        if tags.get('tunnel') not in {None,'no'} or tags.get('covered') not in {None,'no'}:continue
        runs=[];run=[]
        for ref in refs:
            if ref in nodes:run.append(nodes[ref])
            else:
                if len(run)>1:runs.append(run)
                run=[]
        if len(run)>1:runs.append(run)
        for coords in runs:
            for line in util.parts(LineString(coords).intersection(clip),'LineString'):
                if line.length==0:continue
                if is_coast:
                    coast.append(util.feature(line,{'kind':'coastline'}));continue
                measured=tags.get('width') is not None
                width=max(1,min(200,util.number(tags.get('width'),{'river':12,'canal':6,'stream':3,'drain':2,'ditch':1}[kind])))
                props={'kind':kind,'name':tags.get('name',''),'width':width,'width_estimated':not measured}
                waterways.append(util.feature(line,props))
                g=transform(util.UNPROJECT,transform(util.PROJECT,line).buffer(width/2,quad_segs=2)).intersection(clip)
                for p in util.parts(g,'Polygon'):water.append(('water',util.feature(p,{'kind':'river','height':0,'min_height':0})))
    return waterways,water,coast


def write_layers(path,surfaces,waterways,coast,ocean):
    from render_rio import write_feature
    water=unary_union([shape(f['geometry']) for l,f in surfaces if l=='water'])
    airports=unary_union([shape(f['geometry']) for l,f in surfaces if l=='landuse' and f['properties'].get('kind')=='aerodrome']).difference(water)
    campus=unary_union([shape(f['geometry']) for l,f in surfaces if l=='commercial' and f['properties'].get('type')=='college']).difference(water).difference(airports)
    commercial=unary_union([shape(f['geometry']) for l,f in surfaces if l in {'commercial','industrial'} and f['properties'].get('type')!='college']).difference(water).difference(airports).difference(campus)
    parks=unary_union([shape(f['geometry']) for l,f in surfaces if l=='landuse' and f['properties'].get('kind')=='park']).difference(water).difference(airports).difference(campus).difference(commercial)
    counts=Counter()
    with path.open('w') as out:
        for layer,g,props in [('water',water,{'kind':'water','height':0,'min_height':0}),('airports',airports,{'kind':'aerodrome'}),('parks',parks,{'kind':'park'}),('commercial',campus,{'type':'college'}),('commercial',commercial,{'type':'commercial'})]:
            for p in util.parts(g,'Polygon'):
                f=util.feature(p,{**props,'area':transform(util.PROJECT,p).area})
                write_feature(out,f,layer);counts[layer]+=1
                if layer in {'parks','airports'}:write_feature(out,f,'landuse');counts['landuse']+=1
        for f in waterways:write_feature(out,f,'waterways',8);counts['waterways']+=1
        for f in coast:write_feature(out,f,'coastline',6);counts['coastline']+=1
        for f in ocean:write_feature(out,f,'ocean_foundations',6);counts['ocean_foundations']+=1
    return dict(counts)


def patch_tiles(original,overlay,replaced):
    temporary=original.with_suffix('.pmtiles.tmp')
    with original.open('rb') as a,overlay.open('rb') as b,temporary.open('wb') as output:
        sa,sb=MmapSource(a),MmapSource(b);ra,rb=Reader(sa),Reader(sb)
        header=ra.header();metadata=ra.metadata()
        layers=[l for l in metadata['vector_layers'] if l['id'] not in replaced]+[l for l in rb.metadata()['vector_layers'] if l['id'] in replaced]
        metadata['vector_layers']=layers
        # A small iterator merge keeps building layers byte-equivalent after protobuf parsing.
        def indexed(source,side):
            for xyz,raw in all_tiles(source):yield zxy_to_tileid(*xyz),side,raw
        writer=Writer(output);last=None;merged=None;n=0
        for tid,side,raw in heapq.merge(indexed(sa,0),indexed(sb,1)):
            if tid!=last:
                if merged is not None and merged.layers:writer.write_tile(last,gzip.compress(merged.SerializeToString(),compresslevel=1,mtime=0))
                merged=vector_tile_pb2.tile();last=tid;n+=1
                if n%3000==0:print(original.name,'surface tiles patched',n,flush=True)
            tile=vector_tile_pb2.tile();tile.ParseFromString(gzip.decompress(raw))
            for layer in tile.layers:
                if (side==0 and layer.name not in replaced) or (side==1 and layer.name in replaced):merged.layers.add().CopyFrom(layer)
        if merged is not None and merged.layers:writer.write_tile(last,gzip.compress(merged.SerializeToString(),compresslevel=1,mtime=0))
        writer.finalize(header,metadata)
    temporary.replace(original)


def main():
    surfaces,_,_,_=pickle.loads((DATA/'geography.pkl').read_bytes())
    raw=pickle.loads((DATA/'osm.pkl').read_bytes())
    waterways,river_areas,coast=stream_features(raw);del raw
    surfaces=surfaces+river_areas
    # Correct bathymetry belongs in the main map's general-tiles source, too.
    from render_rio import bathymetry
    ocean=bathymetry(surfaces,force=True)
    path=DATA/'surface_layers.jsonl';counts=write_layers(path,surfaces,waterways,coast,ocean)
    (DATA/'render_surfaces.pkl').write_bytes(pickle.dumps(surfaces,protocol=5))
    util.save(DATA/'waterways.geojson',util.collection(waterways))
    overlay=DATA/'surface_layers.pmtiles'
    cmd=['tippecanoe','-o',str(overlay),'-Z6','-z15','-r1','--force','--read-parallel','--no-feature-limit','--no-tile-size-limit',
        '--no-tiny-polygon-reduction-at-maximum-zoom','--full-detail=14','--low-detail=12','--simplify-only-low-zooms','--buffer=8',
        '--clip-bounding-box='+','.join(map(str,VISUAL_BBOX)),str(path)]
    subprocess.run(cmd,check=True,env={**os.environ,'TIPPECANOE_MAX_THREADS':'4'})
    patch_tiles(OUT/'RIO.pmtiles',overlay,{'water','parks','airports','commercial','landuse','waterways','coastline','ocean_foundations'})
    patch_tiles(OUT/'RIO_foundations.pmtiles',overlay,{'ocean_foundations'})
    util.save(DATA/'surface_audit.json',{'source_feature_counts':counts,'river_widths':'OSM width where available; otherwise estimated by waterway type',
        'ocean_foundations_source':'main RIO.pmtiles and foundations archive','green_compatibility':'parks/airports plus landuse aliases for Railyard'})
    print('Surface layers corrected',flush=True)

if __name__=='__main__':main()
