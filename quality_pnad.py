"""Published PNAD aggregate controls and weighted informal activity composition."""
from collections import Counter
import json
import zipfile
import pandas as pd
from map_settings import DATA

# Broad PNAD group -> compatible CNAE/CNEFE classes. Within-group shares are a
# RAIS proxy; PNAD does not measure the fine classes or their local destinations.
GROUPS={1:['agriculture'],2:['industry','utilities'],3:['construction'],
    4:['retail','wholesale','vehicle_trade'],5:['transport'],6:['hotel','food'],
    7:['office','business_services'],8:['public_admin'],9:['education','health'],
    10:['entertainment','personal_services'],11:['domestic'],12:['other']}


def informal_composition(reports):
    raw=DATA/'quality_sources'/'pnad'
    cached=DATA/'quality_prepared'/'pnad_informal_activity.json'
    if cached.exists():result=json.loads(cached.read_text())
    else:
        docs=raw/'docs'
        with zipfile.ZipFile(raw/'dictionary.zip') as archive:archive.extractall(docs)
        dictionary=pd.read_excel(docs/'dicionario_PNADC_microdados_trimestral.xls',header=None).fillna('')
        fields={'UF','RM_RIDE','V1028','VD4002','VD4009','VD4010','V4019'}
        specs={str(r[2]):slice(int(r[0])-1,int(r[0])-1+int(r[1])) for _,r in dictionary.iterrows() if str(r[2]) in fields}
        if set(specs)!=fields:raise ValueError('Incomplete PNAD dictionary')
        weights=Counter();samples=Counter();occupied=0.;informal=0.
        with zipfile.ZipFile(raw/'PNADC_022026.zip') as archive:
            with archive.open('PNADC_022026.txt') as source:
                for line in source:
                    if line[specs['UF']]!=b'33' or line[specs['RM_RIDE']]!=b'33':continue
                    values={k:line[s].decode('ascii').strip() for k,s in specs.items()}
                    if values['VD4002']!='1':continue
                    weight=float(values['V1028']);occupied+=weight
                    position=int(values['VD4009'])
                    is_informal=position in (2,4,10) or (position in (8,9) and values['V4019']=='2')
                    if not is_informal:continue
                    group=int(values['VD4010'] or 12)
                    if group not in GROUPS:raise ValueError('Unexpected PNAD activity')
                    weights[group]+=weight;samples[group]+=1;informal+=weight
        result={'period':'2026Q2','territory':'UF=33, RM_RIDE=33','occupied_expanded':occupied,
            'informal_expanded':informal,'informality_microdata':informal/occupied,
            'definition':'VD4009 in 2,4,10; or 8,9 with V4019=2; weight V1028',
            'groups':[{'group':k,'expanded_informal':weights[k],'sample_records':samples[k],
                'share':weights[k]/informal} for k in sorted(GROUPS)]}
        cached.write_text(json.dumps(result,indent=2)+'\n')
    rais=pd.read_parquet(DATA/'quality_prepared'/'rais_postal_activity.parquet').groupby('activity').active_links.sum()
    shares={};rows=[]
    for group in result['groups']:
        kinds=GROUPS[group['group']];counts=[float(rais.get(k,0)) for k in kinds]
        if not sum(counts):counts=[1.]*len(kinds)
        for kind,count in zip(kinds,counts):
            share=group['share']*count/sum(counts);shares[kind]=share
            rows.append({**group,'activity':kind,'fine_activity_share':share,
                'fine_split':'RAIS formal activity composition proxy' if len(kinds)>1 else 'direct broad-group mapping'})
    pd.DataFrame(rows).to_csv(reports/'informal_activity.csv',index=False)
    (reports/'pnad_microdata_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return shares,result
