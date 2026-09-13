"""Check actual mod URLs against the local server; does not launch the game."""
import gzip
import http.client
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

import mapbox_vector_tile
import mercantile

ROOT=Path(__file__).resolve().parent
PORT=18080


def request(path, method='GET'):
    c=http.client.HTTPConnection('127.0.0.1',PORT,timeout=20)
    try:
        c.request(method,path)
        r=c.getresponse()
        return r.status,dict(r.getheaders()),r.read()
    finally:c.close()


def main():
    # Execute the delivered entry point and capture the API calls it makes.
    script="""
const fs=require('fs'), vm=require('vm');
const calls={};
const api={registerCity:c=>calls.city=c,
 cities:{registerTab:tab=>calls.tab=tab,setCityDataFiles:(code,files)=>calls.data={code,files}},
 map:{setTileURLOverride:c=>calls.tiles=c,
 setDefaultLayerVisibility:(code,layers)=>calls.visibility={code,layers},
 registerSource:(id,source)=>calls.source={id,source},registerLayer:layer=>calls.layer=layer},
 hooks:{onMapReady:fn=>fn({setMaxBounds:b=>calls.bounds=b})},utils:{getCityCode:()=> 'RIO'}};
vm.runInNewContext(fs.readFileSync('mod/index.js','utf8'),
 {window:{SubwayBuilderAPI:api},console:{log(){},error(m){throw Error(m)}}});
process.stdout.write(JSON.stringify(calls));
"""
    calls=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT))
    config=json.loads((ROOT/'build/RIO/config.json').read_text())
    assert calls['city']['code']==calls['data']['code']==calls['tiles']['cityCode']==config['code']
    assert calls['city']['initialViewState']==config['initialViewState']
    assert calls['visibility']['layers']=={'buildingFoundations':True,'oceanFoundations':True}
    assert calls['source']['source']['bounds']==[-44.06,-23.24,-42.67,-22.40]
    proc=subprocess.Popen([sys.executable,'-u','serve_rio.py','--port',str(PORT)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    report={'in_game_test':False,'api_registration_calls_checked':True,'endpoints':{}}
    try:
        for _ in range(100):
            if proc.poll() is not None:
                raise RuntimeError(proc.stderr.read().decode())
            try:
                if request('/data/RIO/config.json')[0]==200:break
            except OSError:pass
            time.sleep(.1)
        else:raise RuntimeError('Local server did not start')
        for key,url in calls['data']['files'].items():
            status,headers,body=request(urlsplit(url).path)
            assert status==200 and headers['Access-Control-Allow-Origin']=='*'
            assert len(body)==int(headers['Content-Length'])
            if key=='buildingsIndex':assert body[:4]==b'SBBI'
            else:assert isinstance(json.loads(gzip.decompress(body) if headers.get('Content-Encoding')=='gzip' else body),dict)
            report['endpoints'][key]={'status':status,'bytes':len(body)}
        tile=mercantile.tile(config['initialViewState']['longitude'],config['initialViewState']['latitude'],15)
        for key in ['tilesUrl','foundationTilesUrl']:
            url=calls['tiles'][key].replace('{z}',str(tile.z)).replace('{x}',str(tile.x)).replace('{y}',str(tile.y))
            status,headers,body=request(urlsplit(url).path)
            assert status==200 and headers['Content-Encoding']=='gzip'
            decoded=mapbox_vector_tile.decode(gzip.decompress(body))
            assert ('buildings' if key=='tilesUrl' else 'foundations') in decoded
            report['endpoints'][key]={'status':status,'layers':list(decoded)}
        status,headers,body=request(urlsplit(calls['city']['mapImageUrl']).path)
        assert status==200 and body[:8]==b'\x89PNG\r\n\x1a\n'
        assert request('/data/RIO/config.json','HEAD')[2]==b''
        assert request('/data/RIO/config.json','OPTIONS')[0]==204
        assert request('/data/RIO/../../README.md')[0]==404
        assert request('/RIO/99/0/0.mvt')[0]==404
        (ROOT/'integration_report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()


if __name__=='__main__':main()
