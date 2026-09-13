"""Fetch OSM waterways across the complete visual extent, including the scenery fringe."""
import json,subprocess
from urllib.parse import urlencode
from map_settings import DATA,VISUAL_BBOX


def main():
    path=DATA/'waterways_osm.json'
    if path.exists():return
    w,s,e,n=VISUAL_BBOX
    query=f'[out:json][timeout:120];way["waterway"~"^(river|stream|canal|drain|ditch)$"]({s},{w},{n},{e});out body geom;'
    temporary=path.with_suffix('.json.download')
    for host in ['https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']:
        result=subprocess.run(['curl','-L','--fail','--compressed','--max-time','150',host+'?'+urlencode({'data':query}),'-o',str(temporary)])
        if result.returncode:continue
        data=json.loads(temporary.read_text())
        if data.get('elements') and not data.get('remark'):
            temporary.replace(path);return
    raise RuntimeError('Could not fetch complete waterways; previous map left in place')

if __name__=='__main__':main()
