"""Serve this map's data and MVT tiles on localhost for the official cities API."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlsplit

from pmtiles.reader import MmapSource, Reader

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'build'/'RIO'
ALLOWED={'config.json','buildings_index.bin','demand_data.json','roads.geojson','runways_taxiways.geojson','ocean_depth_index.json.gz'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    files=[(DATA/name).open('rb') for name in ['RIO.pmtiles','RIO_foundations.pmtiles']]
    readers={name:Reader(MmapSource(f)) for name,f in zip(['RIO','RIO_foundations'],files)}

    class Handler(BaseHTTPRequestHandler):
        def send_headers(self,status,size,kind,encoding=None):
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(size))
            self.send_header('Access-Control-Allow-Origin','*')
            self.send_header('Access-Control-Allow-Methods','GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type')
            self.send_header('Access-Control-Allow-Private-Network','true')
            self.send_header('Cache-Control','no-cache')
            if encoding:self.send_header('Content-Encoding',encoding)
            self.end_headers()

        def do_OPTIONS(self):
            self.send_headers(204,0,'text/plain')

        def do_HEAD(self):
            self.respond(head=True)

        def do_GET(self):
            self.respond(head=False)

        def respond(self,head):
            path=urlsplit(self.path).path
            match=re.fullmatch(r'/(RIO|RIO_foundations)/(\d{1,2})/(\d+)/(\d+)\.mvt',path)
            if match:
                name,z,x,y=match.groups();z,x,y=map(int,(z,x,y))
                if not (0<=z<=15 and 0<=x<2**z and 0<=y<2**z):
                    self.send_headers(404,0,'text/plain');return
                tile=readers[name].get(z,x,y)
                if tile is None:
                    self.send_headers(204,0,'application/vnd.mapbox-vector-tile');return
                self.send_headers(200,len(tile),'application/vnd.mapbox-vector-tile','gzip')
                if not head:self.wfile.write(tile)
                return
            name=path.removeprefix('/data/RIO/')
            if path.startswith('/data/RIO/') and name in ALLOWED:
                file=DATA/name
                kind='application/octet-stream' if name.endswith('.bin') else 'application/json; charset=utf-8'
            elif path=='/RIO/thumbnail.png':
                file=ROOT/'preview.png';kind='image/png'
            else:
                self.send_headers(404,0,'text/plain');return
            if not file.is_file():
                self.send_headers(404,0,'text/plain');return
            self.send_headers(200,file.stat().st_size,kind,'gzip' if file.suffix=='.gz' else None)
            if not head:
                with file.open('rb') as f:
                    while block:=f.read(1024*1024):self.wfile.write(block)

    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Rio tile/data server: http://127.0.0.1:{args.port} (Ctrl+C to stop)',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        for f in files:f.close()


if __name__=='__main__':main()
