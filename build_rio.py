"""Generate and overwrite the single Rio map package."""
import argparse
import json
import shutil
import subprocess
import sys
from map_settings import ROOT, DATA, OUT, PLAY_BBOX, VISUAL_BBOX, VERSION
from geography import save


def download(url, path):
    if path.exists(): return
    temporary=path.with_suffix(path.suffix+'.download')
    subprocess.run(['curl','-L','--fail','--retry','3',url,'-o',str(temporary)],check=True)
    temporary.replace(path)


def sources(pbf):
    DATA.mkdir(exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    if not (DATA/'osm.pkl').exists():
        import prepare_rio
        prepare_rio.configure()
        if pbf:
            import geography
            geography.extract(pbf)
        elif (DATA/'osm_core.pkl').exists() and all((DATA/f'fringe_{s}.json.gz').exists() for s in ['north','south','east','west']):
            prepare_rio.merge_extracts()
        else:
            path=DATA/'sudeste.osm.pbf'
            download('https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf',path)
            import geography
            geography.extract(path)
    if not (DATA/'overture.parquet').exists():
        subprocess.run([sys.executable,str(ROOT/'fetch_overture.py')],check=True,cwd=ROOT)
    if not (DATA/'census.pkl').exists():
        import geopandas as gpd
        path=DATA/'RJ_setores_CD2022.gpkg'
        download('https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/malha_com_atributos/setores/gpkg/UF/RJ/RJ_setores_CD2022.gpkg',path)
        gpd.read_file(path,bbox=PLAY_BBOX).to_pickle(DATA/'census.pkl')
    download('https://www.gmrt.org/services/GridServer?minlongitude=-44.07&maxlongitude=-42.66&minlatitude=-23.25&maxlatitude=-22.39&format=netcdf&resolution=default&layer=topo',DATA/'gmrt.nc')


def configure():
    census=json.loads((DATA/'population_audit.json').read_text())
    config={'name':'Rio de Janeiro','code':'RIO','country':'BR','thumbnailBbox':[-43.80,-23.08,-42.88,-22.59],
        'description': 'Build a rail network across Greater Rio, connecting Rio de Janeiro, the Baixada Fluminense, Niterói, São Gonçalo and the wider metropolitan area.',
        'population':census['population'],'initialViewState':{'zoom':10.5,'latitude':-22.84,'longitude':-43.30,'bearing':0},
        'creator':'guylherme','version':VERSION,'minZoom':8,'buildingZoomOffset':-.75}
    save(OUT/'config.json',config)
    city={k:config[k] for k in ['name','code','description','population','initialViewState','minZoom','buildingZoomOffset']}
    (ROOT/'mod/index.js').write_text((ROOT/'mod/template.js').read_text().replace('__RIO_CITY_CONFIG__',json.dumps(city,ensure_ascii=False)))
    save(ROOT/'coverage.json',{'playable':PLAY_BBOX,'visual':VISUAL_BBOX,'outside_playable':'visual-only scenery; no census demand or building collision index'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--surfaces-only',action='store_true',help='Repair water, coast and green layers, then package; reuse buildings and demand')
    mode.add_argument('--employment-only',action='store_true',help='Recalibrate jobs and workers from official benchmarks, then package; reuse geography')
    mode.add_argument('--package-only',action='store_true',help='Package already generated files without tests; skip map regeneration')
    parser.add_argument('--pbf',type=str,help='Local OSM regional extract, used when the extracted OSM cache is absent')
    args=parser.parse_args()
    if args.surfaces_only:
        from repair_surfaces import main as repair
        repair()
        configure()
    elif args.employment_only:
        from employment import main as calibrate
        calibrate()
        configure()
    elif not args.package_only:
        if not shutil.which('tippecanoe'):parser.error('Install tippecanoe first: brew install tippecanoe')
        sources(args.pbf)
        import prepare_rio
        prepare_rio.geography();prepare_rio.buildings()
        (OUT/'demand_data.json').unlink(missing_ok=True)
        from census_demand import generate
        generate()
        configure()
        from render_rio import run
        run()
    else:
        configure()
    subprocess.run([sys.executable,str(ROOT/'preview_rio.py')],check=True,cwd=ROOT)
    from package_rio import main as package
    package()
    print('Ready: '+str(ROOT/'dist/RIO.zip'),flush=True)


if __name__=='__main__':main()
