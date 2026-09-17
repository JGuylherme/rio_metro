"""Independent comparison to Census 2022 automobile commute duration bins."""
import json
import numpy as np
import pandas as pd
from map_settings import ROOT

BINS=[(19429,0,300),(79189,300,900),(79190,900,1800),(19431,1800,3600),
      (19432,3600,7200),(79191,7200,14400),(79192,14400,float('inf'))]


def compare(flows,reports):
    source=ROOT/'sources/census_car_travel_2022.json'
    if not source.exists():raise ValueError('Missing Census travel validation source; run fetch_quality_sources.py --kind census')
    records=json.loads(source.read_text())[0]['resultados'];counts={}
    for result in records:
        classification=next(c for c in result['classificacoes'] if c['id']=='537')
        category=int(next(iter(classification['categoria'])))
        for row in result['series']:
            raw=row['serie']['2022'];counts[row['localidade']['id'],category]=int(raw) if raw.isdigit() else 0 if raw=='-' else None
    rows=[]
    for code,group in flows.groupby('origin'):
        observed=[counts.get((code,category)) for category,_,_ in BINS]
        if any(x is None for x in observed):continue
        denominator=sum(observed)
        if denominator==0:continue
        for (category,lower,upper),count in zip(BINS,observed):
            model=int(group.loc[(group.seconds>lower)&(group.seconds<=upper),'size'].sum())
            rows.append({'municipality_code':code,'seconds_above':lower,'seconds_at_most':upper,
                'census_car_commuters_2022':count,'census_share':count/denominator,
                'modeled_all_commuters_road_time':model,'modeled_share':model/group['size'].sum(),
                'share_difference_percentage_points':100*(model/group['size'].sum()-count/denominator),
                'interpretation':'Diagnostic only: 2022 automobile users returning >=3 days/week versus all modeled commuters, static road times, no congestion; different universes and boundary.'})
    pd.DataFrame(rows).to_csv(reports/'travel_time_census_comparison.csv',index=False)
