"""Fetch pinned official inputs, restricted to represented municipalities."""
import argparse
import csv
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from map_settings import ROOT, DATA

CNEFE_BASE = 'https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/GeoJSON/'
RAIS_URL = 'ftp://ftp.mtps.gov.br/pdet/microdados/RAIS/2024/RAIS_ESTAB_PUB.7z'
CENSUS_BASE = 'https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Microdados_e_Areas_de_Ponderacao/'
RAW = DATA / 'quality_sources'


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.download')
        subprocess.run(['curl', '-sS', '-L', '--fail', '--retry', '3', '--max-time', '1800', url, '-o', str(temporary)], check=True)
        temporary.replace(path)
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    print(f'Cached {path.name}: {path.stat().st_size:,} bytes', flush=True)
    return {'path': str(path.relative_to(ROOT)), 'url': url, 'bytes': path.stat().st_size, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['all', 'cnefe', 'rais', 'census', 'pnad'], default='all')
    args = parser.parse_args()
    tasks = []
    if args.kind in ('all', 'cnefe'):
        tasks.append((CNEFE_BASE + 'Dicionario_CNEFE_Censo_2022_GeoJSON.xls', RAW / 'cnefe' / 'dictionary.xls'))
        codes = sorted({row['municipality_code'] for row in csv.DictReader((ROOT / 'resident_workers_by_municipality.csv').open())})
        for code in codes:
            name = f'qg_810_endereco_Munic{code}.json.zip'
            tasks.append((CNEFE_BASE + 'Municipio_20240910/' + name, RAW / 'cnefe' / name))
    if args.kind in ('all', 'rais'):
        tasks.append((RAIS_URL, RAW / 'rais' / 'RAIS_ESTAB_PUB_2024.7z'))
    if args.kind in ('all', 'census'):
        tasks.append(('https://servicodados.ibge.gov.br/api/v3/agregados/10330/periodos/2022/variaveis/13376?localidades=N6%5BN3%5B33%5D%5D&classificacao=537%5Ball%5D%7C2088%5B79197%5D%7C86%5B95251%5D%7C469%5B79176%5D',ROOT/'sources/census_car_travel_2022.json'))
        tasks.extend([
            (CENSUS_BASE + 'Microdados_de_acesso_Publico/csv/33_RJ.zip', RAW / 'census' / '33_RJ.zip'),
            (CENSUS_BASE + 'Documentacao/Layout%20e%20dicion%C3%A1rio/Layout%20Microdados%20CD2022%20-%20acesso%20P%C3%BAblico.xlsx', RAW / 'census' / 'layout_public.xlsx'),
            (CENSUS_BASE + 'Documentacao/Layout%20e%20dicion%C3%A1rio/Dicion%C3%A1rio%20de%20Vari%C3%A1veis%20-%20Microdados%20CD2022.pdf', RAW / 'census' / 'dictionary.pdf'),
            (CENSUS_BASE + '1_Atualizacoes_20260914.pdf', RAW / 'census' / 'updates_20260914.pdf')])
        historical='https://ftp.ibge.gov.br/Censos/Censo_Demografico_2010/Resultados_Gerais_da_Amostra/Microdados/'
        tasks.extend([(historical+'RJ.zip',RAW/'census2010'/'RJ.zip'),
                      (historical+'Documentacao.zip',RAW/'census2010'/'Documentacao.zip')])
    if args.kind in ('all','pnad'):
        pnad='https://ftp.ibge.gov.br/Trabalho_e_Rendimento/Pesquisa_Nacional_por_Amostra_de_Domicilios_continua/Trimestral/Microdados/'
        tasks.extend([(pnad+'2026/PNADC_022026.zip',RAW/'pnad'/'PNADC_022026.zip'),
                      (pnad+'Documentacao/Dicionario_e_input_20221031.zip',RAW/'pnad'/'dictionary.zip')])
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda task: download(*task), tasks))
    target = ROOT / 'sources' / f'quality_downloads_{args.kind}.json'
    target.write_text(json.dumps({'source_vintages': {'cnefe': '2022, release 20240910', 'rais': '2024 second processing, file 20260518',
        'census_public': '2022, public layout updated 20260914', 'od_historical': 'Census 2010 sample, RJ',
        'pnad': '2026Q2; weights from the downloaded file'}, 'files': records}, indent=2) + '\n')


if __name__ == '__main__':
    main()
