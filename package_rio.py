"""Overwrite the delivery ZIP without running tests."""
import zipfile
from map_settings import ROOT,OUT
FILES=['config.json','demand_data.json','roads.geojson','runways_taxiways.geojson','buildings_index.bin','RIO.pmtiles','RIO_foundations.pmtiles','ocean_depth_index.json.gz']

def main():
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    temporary=dist/'RIO.zip.tmp'
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for name in FILES:
            print('Empacotando '+name,flush=True)
            archive.write(OUT/name,name)
    temporary.replace(dist/'RIO.zip')
    print('Pronto: '+str(dist/'RIO.zip'),flush=True)

if __name__=='__main__':main()
