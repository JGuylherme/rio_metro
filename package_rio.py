"""Build and verify the two GitHub Release assets without rebuilding map data."""
import json
import shutil
import zipfile
from release_demand import export_demand
from map_settings import ROOT,OUT,VERSION
FILES=['config.json','demand_data.json','roads.geojson','runways_taxiways.geojson','buildings_index.bin','RIO.pmtiles','RIO_foundations.pmtiles','ocean_depth_index.json.gz']

def main():
    manifest=ROOT/'manifest.json'
    compatibility=json.loads(manifest.read_text())['dependencies']['subway-builder']
    if not isinstance(compatibility,str) or not compatibility.strip():
        raise ValueError('manifest.json must declare subway-builder compatibility')
    config=json.loads((OUT/'config.json').read_text())
    if config.get('code')!='RIO' or config.get('version')!=VERSION:
        raise ValueError('Map config must use code RIO and version '+VERSION)
    for name in FILES:
        if not (OUT/name).is_file() or (OUT/name).stat().st_size==0:
            raise ValueError('Missing or empty map file: '+name)
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    demand=export_demand(json.loads((OUT/'demand_data.json').read_text()))
    demand_bytes=json.dumps(demand,separators=(',',':'),ensure_ascii=False).encode()
    print('Residentes de demanda = pops = '+str(sum(p['size'] for p in demand['pops'])),flush=True)
    temporary=dist/'RIO.zip.tmp'
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for name in FILES:
            print('Empacotando '+name,flush=True)
            if name=='demand_data.json':archive.writestr(name,demand_bytes)
            else:archive.write(OUT/name,name)
    with zipfile.ZipFile(temporary) as archive:
        if archive.namelist()!=FILES or archive.testzip() is not None:
            raise ValueError('Invalid map ZIP')
    temporary.replace(dist/'RIO.zip')
    shutil.copyfile(manifest,dist/'manifest.json')
    print('Pronto: '+str(dist/'RIO.zip'),flush=True)
    print('Manifest separado: '+str(dist/'manifest.json'),flush=True)

if __name__=='__main__':main()
