"""Update this Rio map in an existing Railyard installation, without touching saves."""
import argparse,gzip,json,re,shutil
from pathlib import Path
from map_settings import ROOT,OUT,DATA


def atomic_copy(source,target,compress=False):
    temporary=target.with_name(target.name+'.rio-update')
    if compress:
        with source.open('rb') as a,gzip.open(temporary,'wb',compresslevel=1) as b:shutil.copyfileobj(a,b)
    else:shutil.copy2(source,temporary)
    temporary.replace(target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tiles',action='store_true',help='Also replace map/foundation tiles and ocean depth index')
    args=parser.parse_args()
    game=Path.home()/'Library/Application Support/metro-maker4'
    loader=game/'mods/mapLoader/index.js'
    if not loader.exists():raise SystemExit('Railyard mapLoader not found; import dist/RIO.zip first.')
    source=loader.read_text()
    match=re.search(r'var config = (\{[^\n]+\});',source)
    if not match:raise SystemExit('Unsupported mapLoader configuration; no changes made.')
    config=json.loads(match.group(1));city=json.loads((OUT/'config.json').read_text())
    places=[p for p in config['places'] if p['code']=='RIO']
    if not places:raise SystemExit('Import dist/RIO.zip in Railyard first.')
    for p in places:p.update({k:city[k] for k in ['country','population','description','initialViewState','minZoom','buildingZoomOffset']})
    backup=DATA/'installation_backup';backup.mkdir(parents=True,exist_ok=True)
    if not (backup/'mapLoader.js').exists():shutil.copy2(loader,backup/'mapLoader.js')
    loader.write_text(source[:match.start(1)]+json.dumps(config,ensure_ascii=False,separators=(',',':'))+source[match.end(1):])
    target=game/'cities/data/RIO'
    for name in ['config.json','demand_data.json']:
        destination=target/name
        compressed=target/(name+'.gz')
        if compressed.exists():destination=compressed
        if destination.exists() and not (backup/destination.name).exists():shutil.copy2(destination,backup/destination.name)
        atomic_copy(OUT/name,destination,compress=destination.suffix=='.gz')
        # Keep both forms synchronized if an older installation left both behind.
        if compressed.exists() and (target/name).exists():atomic_copy(OUT/name,target/name)
    if args.tiles:
        tiles=Path.home()/'Library/Application Support/railyard/tiles'
        if not tiles.is_dir():raise SystemExit('Railyard tiles directory not found; import ZIP instead.')
        for name in ['RIO.pmtiles','RIO_foundations.pmtiles']:
            if (tiles/name).exists() and not (backup/name).exists():shutil.copy2(tiles/name,backup/name)
            atomic_copy(OUT/name,tiles/name)
        depth=target/'ocean_depth_index.json.gz'
        if depth.exists() and not (backup/depth.name).exists():shutil.copy2(depth,backup/depth.name)
        atomic_copy(OUT/depth.name,depth)
        if (target/'ocean_depth_index.json').exists():
            with gzip.open(OUT/depth.name,'rb') as a,(target/'ocean_depth_index.json').open('wb') as b:shutil.copyfileobj(a,b)
    shutil.copytree(ROOT/'menu_mod',game/'mods/00-rio-menu',dirs_exist_ok=True)
    print('Rio atualizado. Reinicie Railyard e jogo para descartar tiles antigos; ative Rio — Brasil e população nos mods, se necessário.')

if __name__=='__main__':main()
