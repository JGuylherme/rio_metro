"""Stream CNEFE units and aggregate anonymous RAIS headcounts before spatial use."""
import argparse
from collections import Counter
import json
import inspect
from pathlib import Path
import re
import unicodedata
import zipfile
import ijson
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from map_settings import ROOT, DATA

RAW = DATA / 'quality_sources'
PREP = DATA / 'quality_prepared'


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower()) if not unicodedata.combining(c))


def activity(cnae):
    code = str(cnae).strip().zfill(7)
    division = int(code[:2]) if code.isdigit() else 0
    if division == 0: return 'other'
    if division <= 3: return 'agriculture'
    if division <= 33: return 'industry'
    if division <= 39: return 'utilities'
    if division <= 43: return 'construction'
    if division == 45: return 'vehicle_trade'
    if division == 46: return 'wholesale'
    if division == 47: return 'retail'
    if division <= 53: return 'transport'
    if division == 55: return 'hotel'
    if division == 56: return 'food'
    if division <= 75: return 'office'
    if division <= 82: return 'business_services'
    if division == 84: return 'public_admin'
    if division == 85: return 'education'
    if division <= 88: return 'health'
    if division <= 93: return 'entertainment'
    if division <= 96: return 'personal_services'
    if division == 97: return 'domestic'
    return 'other'


def address_activity(species, name):
    if species == 3: return 'agriculture'
    if species == 4: return 'education'
    if species == 5: return 'health'
    if species == 8: return 'personal_services'
    name = normalized(name)
    rules = [
        ('health', r'hospital|clinica|laboratorio|odont|saude|medic'),
        ('education', r'escola|colegio|universidade|creche|ensino|faculdade'),
        ('industry', r'industr|fabrica|metalurg|refinaria|siderurg|estaleiro'),
        ('utilities', r'subestacao|tratamento de agua|tratamento de esgoto|usina'),
        ('wholesale', r'atacad|distribuid|deposito|armazem'),
        ('transport', r'aeroporto|terminal|transport|logistica|correios|ferrovia|rodoviaria'),
        ('hotel', r'hotel|pousada|hostel|motel'),
        ('food', r'restaurante|lanchonete|pizzaria|padaria|bar |churrasc|sorveteria'),
        ('retail', r'shopping|mercado|supermercado|loja|farmacia|drogaria|comercio|hortifruti'),
        ('vehicle_trade', r'oficina|autopecas|borracharia|concessionaria|posto de gasolina'),
        ('public_admin', r'prefeitura|secretaria|delegacia|batalhao|quartel|tribunal|forum'),
        ('entertainment', r'estadio|museu|teatro|cinema|clube|academia'),
        ('personal_services', r'salao|barbearia|lavanderia|igreja|templo'),
        ('construction', r'construtora|engenharia civil'),
        ('office', r'banco|escritorio|advoc|contab|seguradora|informatica'),
    ]
    for kind, pattern in rules:
        if re.search(pattern, name): return kind
    return 'other'


def prepare_cnefe():
    PREP.mkdir(parents=True, exist_ok=True)
    outputs = [PREP / 'cnefe_units.parquet', PREP / 'cnefe_audit.json']
    from quality_cache import fingerprint
    signature=fingerprint(sorted((RAW/'cnefe').glob('*.json.zip')),inspect.getsource(prepare_cnefe)+inspect.getsource(address_activity)+inspect.getsource(normalized))
    stamp=PREP/'cnefe.sha256'
    if all(p.exists() for p in outputs) and stamp.exists() and stamp.read_text()==signature: return
    writer = None
    rows = []; stats = Counter(); municipalities = Counter()
    columns = ['unit_id','municipality','sector','cep','species','geo_level','building_type','lon','lat','activity']
    def flush():
        nonlocal writer
        if not rows: return
        frame = pd.DataFrame(rows, columns=columns)
        table = pa.Table.from_pandas(frame, preserve_index=False)
        if writer is None: writer = pq.ParquetWriter(str(outputs[0])+'.tmp', table.schema, compression='zstd')
        writer.write_table(table); rows.clear()
    for path in sorted((RAW/'cnefe').glob('*.json.zip')):
        with zipfile.ZipFile(path) as archive:
            with archive.open(archive.namelist()[0]) as source:
                for feature in ijson.items(source, 'features.item', use_float=True):
                    p=feature['properties']; stats['raw_units']+=1
                    kind=int(p['COD_ESPECIE']); precision=int(p['NV_GEO_COORD'])
                    stats[f'species_{kind}']+=1;stats[f'geo_level_{precision}']+=1
                    if kind == 7: stats['excluded_under_construction']+=1; continue
                    coordinates=(feature.get('geometry') or {}).get('coordinates')
                    if not coordinates or len(coordinates)!=2:stats['missing_coordinates']+=1;continue
                    lon,lat=map(float,coordinates)
                    if not -45<lon<-40 or not -25<lat<-20:stats['invalid_coordinates']+=1;continue
                    municipality=str(p['COD_MUNICIPIO']);municipalities[municipality]+=1
                    # Original CNEFE sectors have an extra processing suffix (P).
                    sector=str(p['COD_SETOR'])[:15]
                    rows.append((str(p['COD_UNICO_ENDERECO']),municipality,sector,str(p.get('CEP') or '').zfill(8),
                        kind,precision,int(p.get('COD_TIPO_ESPECI') or p.get('COD_TIPO_ESPECIE') or 0),lon,lat,
                        'residential' if kind in (1,2) else address_activity(kind,p.get('DSC_ESTABELECIMENTO',''))))
                    if len(rows)>=100000:flush()
        print('Prepared CNEFE',path.name,stats['raw_units'],flush=True)
    flush()
    if writer is None:raise ValueError('No CNEFE units')
    writer.close();Path(str(outputs[0])+'.tmp').replace(outputs[0])
    outputs[1].write_text(json.dumps({'counts':dict(stats),'municipal_units':dict(municipalities),
        'interpretation':'One record per address species, not employees. Levels 1/2 address coordinates; 3 estimated; 4–6 coarse. No names or personal attributes retained.'},indent=2)+'\n')
    stamp.write_text(signature)


def prepare_rais():
    PREP.mkdir(parents=True, exist_ok=True)
    from quality_cache import fingerprint
    codes=pd.read_csv(ROOT/'resident_workers_by_municipality.csv',dtype={'municipality_code':str}).municipality_code
    signature=fingerprint([RAW/'rais'/'RAIS_ESTAB_PUB_2024.7z'],inspect.getsource(prepare_rais)+inspect.getsource(activity)+','.join(sorted(codes)))
    stamp=PREP/'rais.sha256'
    if (PREP/'rais_postal_activity.parquet').exists() and stamp.exists() and stamp.read_text()==signature:return
    import py7zr
    folder=RAW/'rais'/'extracted';path=folder/'RAIS_ESTAB_PUB.COMT'
    if not path.exists() or not stamp.exists() or stamp.read_text()!=signature:
        with py7zr.SevenZipFile(RAW/'rais'/'RAIS_ESTAB_PUB_2024.7z') as archive:archive.extractall(path=folder)
    codes=pd.read_csv(ROOT/'resident_workers_by_municipality.csv',dtype={'municipality_code':str}).municipality_code
    lookup={code[:6]:code for code in codes};parts=[];stats=Counter()
    wanted={'Município - Código':'municipality','CEP Estab':'cep','CNAE 2.0 Subclasse - Codigo':'cnae',
            'Qtd Vínculos Ativos':'active_links','Tamanho Estabelecimento - Código':'size_band',
            'Bairros RJ - Código':'rio_bairro'}
    for chunk in pd.read_csv(path,encoding='latin1',sep=',',usecols=list(wanted),dtype=str,chunksize=250000):
        stats['national_rows_scanned']+=len(chunk)
        chunk=chunk.rename(columns=wanted)
        chunk=chunk[chunk.municipality.str.strip().isin(lookup)].copy()
        if chunk.empty:continue
        chunk['municipality']=chunk.municipality.str.strip().map(lookup)
        chunk['active_links']=pd.to_numeric(chunk.active_links,errors='raise')
        if chunk.active_links.isna().any() or (chunk.active_links<0).any():raise ValueError('Invalid RAIS links')
        stats['represented_establishments']+=len(chunk)
        chunk=chunk[chunk.active_links>0].copy();stats['positive_establishments']+=len(chunk)
        chunk['cep']=chunk.cep.fillna('').str.strip().str.zfill(8)
        chunk['cnae']=chunk.cnae.str.strip().str.zfill(7)
        chunk['activity']=chunk.cnae.map(activity)
        chunk['establishments']=1
        parts.append(chunk.groupby(['municipality','cep','cnae','activity','size_band','rio_bairro'],dropna=False)[['active_links','establishments']].sum().reset_index())
    data=pd.concat(parts).groupby(['municipality','cep','cnae','activity','size_band','rio_bairro'],dropna=False)[['active_links','establishments']].sum().reset_index()
    temporary=PREP/'rais_postal_activity.tmp.parquet'
    data.to_parquet(temporary,index=False)
    temporary.replace(PREP/'rais_postal_activity.parquet')
    data.groupby(['municipality','activity'])[['active_links','establishments']].sum().to_csv(ROOT/'rais_activity_by_municipality.csv')
    stats['active_links']=int(data.active_links.sum())
    (PREP/'rais_audit.json').write_text(json.dumps({'year':2024,'processing':'second, includes public administration','counts':dict(stats),
        'measured_location':'declared establishment municipality and CEP, not verified individual workplaces',
        'matching':'postal/activity allocation only; anonymous RAIS has no shared establishment identifier with CNEFE'},indent=2)+'\n')
    print('RAIS prepared:',dict(stats),flush=True)
    stamp.write_text(signature)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--kind',choices=['all','cnefe','rais'],default='all');args=parser.parse_args()
    if args.kind in ('all','cnefe'):prepare_cnefe()
    if args.kind in ('all','rais'):prepare_rais()
