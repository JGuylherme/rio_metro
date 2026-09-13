"""Download reproducible official employment benchmarks (latest checked 2026-09-11)."""
import json,subprocess
from urllib.parse import urlencode
from map_settings import DATA
SOURCES={
 'pnad_current.json':'https://apisidra.ibge.gov.br/values/t/4093/n3/33/n7/3301/n6/3304557/v/1641,4090,4097,4099,12466/p/202602/c2/6794',
 'population_current.json':'https://apisidra.ibge.gov.br/values/t/5918/n3/33/n7/3301/n6/3304557/v/606/p/202602/c58/95253',
 'cempre_current.json':'https://apisidra.ibge.gov.br/values/t/9509/n6/in%20n3%2033/v/707,708/p/2024',
 'rais_bairros_2023.geojson':'https://services1.arcgis.com/OlP4dGNtIcnD3RYf/arcgis/rest/services/Dashboard_todas_cnaes_variacao/FeatureServer/2/query?'+urlencode({'f':'geojson','where':"ano=2023 AND codigo_atividade='Todos'",'outFields':'*','outSR':4326,'resultRecordCount':2000})}

def main():
    folder=DATA/'employment_sources';folder.mkdir(parents=True,exist_ok=True)
    for name,url in SOURCES.items():
        path=folder/name
        if path.exists():continue
        temporary=path.with_suffix(path.suffix+'.download')
        subprocess.run(['curl','-L','--fail','--retry','3','--max-time','120',url,'-o',str(temporary)],check=True)
        json.loads(temporary.read_text());temporary.replace(path)
    (folder/'sources.json').write_text(json.dumps({'checked_on':'2026-09-11','urls':SOURCES},indent=2)+'\n')

if __name__=='__main__':main()
