"""Observed containment, explicitly historical pair priors, exact integer margins."""
from collections import Counter
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import maximum_flow
from scipy.sparse import coo_matrix
from census_workers import municipal_series
from employment import integer_totals
from map_settings import ROOT, DATA


def historical_od():
    target=ROOT/'sources'/'census_od_2010_rj.csv'
    if target.exists():return pd.read_csv(target,dtype={'origin':str,'destination':str})
    raw=DATA/'quality_sources'/'census2010'
    docs=raw/'docs'
    layout=list(docs.rglob('Layout_microdados_Amostra.xls'))
    if not layout:
        with zipfile.ZipFile(raw/'Documentacao.zip') as archive:archive.extractall(docs)
        layout=list(docs.rglob('Layout_microdados_Amostra.xls'))
    sheet=pd.read_excel(layout[0],sheet_name='PESS',header=None).fillna('')
    wanted={'V0001','V0002','V0010','V0660','V6604','V0661','V0662'}
    specs={str(row[0]):slice(int(row[7])-1,int(row[8])) for _,row in sheet.iterrows() if str(row[0]) in wanted}
    if set(specs)!=wanted:raise ValueError('Unexpected official 2010 layout')
    weights=Counter();samples=Counter();excluded=Counter()
    with zipfile.ZipFile(raw/'RJ.zip') as archive:
        with archive.open('RJ/Amostra_Pessoas_33.txt') as source:
            for line in source:
                values={k:line[span].decode('ascii').strip() for k,span in specs.items()}
                status=values['V0660']
                if not status:continue
                weight=int(values['V0010'])/1e13
                origin=values['V0001']+values['V0002']
                if status=='2':destination=origin
                elif status=='3':destination=values['V6604']
                else:excluded[status]+=weight;continue
                if len(destination)!=7 or not destination.isdigit():excluded['unknown_destination']+=weight;continue
                key=(origin,destination);weights[key]+=weight;samples[key]+=1
    rows=[{'origin':o,'destination':d,'expanded_workers_2010':value,'sample_records':samples[o,d]} for (o,d),value in sorted(weights.items())]
    result=pd.DataFrame(rows);result.to_csv(target,index=False)
    (ROOT/'sources'/'census_od_2010_notes.json').write_text(json.dumps({'year':2010,'universe':'worked outside own home, one municipality; V0660=2 or 3',
        'expansion':'V0010 implied 13 decimal places; municipality V0001+V0002, destination V6604',
        'excluded_weighted':dict(excluded),'warning':'Sample expansion, historical structure. Not an enumerated matrix or 2022 observations.'},indent=2)+'\n')
    return result


def fit_sparse(rows, cols, initial, row_targets, col_targets, tolerance=1e-7, iterations=20000):
    rows=np.asarray(rows,int);cols=np.asarray(cols,int);values=np.asarray(initial,float).copy()
    r=np.asarray(row_targets,float);c=np.asarray(col_targets,float)
    if not all(np.isfinite(a).all() for a in [values,r,c]):raise ValueError('Non-finite transport input')
    if not np.isclose(r.sum(),c.sum(),atol=1e-5,rtol=0):raise ValueError('Incompatible margin totals')
    if np.any(values<0) or np.any(r<0) or np.any(c<0):raise ValueError('Negative transport mass')
    if r.sum()==0:return np.zeros(len(values))
    for iteration in range(iterations):
        current=np.bincount(rows,weights=values,minlength=len(r))
        if np.any((r>0)&(current==0)):raise ValueError('Origin outside routing support')
        values*=np.divide(r,current,out=np.zeros(len(r)),where=current>0)[rows]
        current=np.bincount(cols,weights=values,minlength=len(c))
        if np.any((c>0)&(current==0)):raise ValueError('Workplace outside routing support')
        values*=np.divide(c,current,out=np.zeros(len(c)),where=current>0)[cols]
        if iteration%20==0:
            error=max(np.max(np.abs(np.bincount(rows,weights=values,minlength=len(r))-r)),
                      np.max(np.abs(np.bincount(cols,weights=values,minlength=len(c))-c)))
            if error<tolerance:return values
    raise ValueError(f'Transport support cannot close margins: residual {error:.6g}')


def round_transport(rows, cols, values, row_targets, col_targets):
    """Integral residual network rounding keeps BOTH margins and floor/ceil bounds."""
    rows=np.asarray(rows,int);cols=np.asarray(cols,int);values=np.asarray(values,float)
    r=np.asarray(row_targets,int);c=np.asarray(col_targets,int)
    floor=np.floor(values+1e-10).astype(int)
    rr=r-np.bincount(rows,weights=floor,minlength=len(r)).astype(int)
    cc=c-np.bincount(cols,weights=floor,minlength=len(c)).astype(int)
    if min(rr.min(),cc.min())<0 or rr.sum()!=cc.sum():raise ValueError('Invalid rounding margins')
    if rr.sum():
        eligible=np.flatnonzero((rr[rows]>0)&(cc[cols]>0)&(values>floor))
        n=len(r)+len(c);source=n;sink=n+1
        matrix=coo_matrix((np.r_[rr,np.ones(len(eligible),dtype=int),cc],
            (np.r_[np.full(len(r),source),rows[eligible],len(r)+np.arange(len(c))],
             np.r_[np.arange(len(r)),len(r)+cols[eligible],np.full(len(c),sink)])),shape=(n+2,n+2)).tocsr().astype(np.int64)
        solution=maximum_flow(matrix,source,sink)
        if solution.flow_value!=rr.sum():raise ValueError('Integer rounding infeasible')
        floor[eligible]+=np.asarray(solution.flow[rows[eligible],len(r)+cols[eligible]]).ravel().astype(int)
    if not np.array_equal(np.bincount(rows,weights=floor,minlength=len(r)).astype(int),r):raise ValueError('Origin rounding mismatch')
    if not np.array_equal(np.bincount(cols,weights=floor,minlength=len(c)).astype(int),c):raise ValueError('Destination rounding mismatch')
    return floor


def bounded_jobs(initial, diagonal, off_rows):
    """Reconcile modeled jobs with measured local containment, retaining raw input."""
    total=int(diagonal.sum()+off_rows.sum());lower=diagonal.astype(int)
    upper=lower+int(off_rows.sum())-off_rows
    if np.any(upper<lower):raise ValueError('Infeasible containment bounds')
    if off_rows.sum()==0:return lower
    lo,hi=0.,max(2.,total/max(float(np.min(initial[initial>0])),1.))
    for _ in range(100):
        middle=(lo+hi)/2;values=np.clip(initial*middle,lower,upper)
        if values.sum()<total:lo=middle
        else:hi=middle
    values=np.clip(initial*hi,lower,upper);result=np.floor(values+1e-8).astype(int)
    missing=total-result.sum()
    candidates=np.flatnonzero(result<upper)
    order=candidates[np.argsort(-(values-result)[candidates],kind='stable')]
    if not 0<=missing<=len(order):raise ValueError('Job reconciliation rounding failed')
    result[order[:missing]]+=1
    return result


def municipal_model(codes, employed, job_weights, job_coverage, config, reports):
    """Census 2022 local/other constraints; 2010 destinations only as a prior."""
    codes=list(codes);n=len(codes);idx={code:i for i,code in enumerate(codes)}
    history=historical_od();matrix=np.zeros((n,n));external=np.zeros(n)
    for row in history.itertuples(index=False):
        if row.origin not in idx or row.origin==row.destination:continue
        i=idx[row.origin]
        if row.destination in idx:matrix[i,idx[row.destination]]+=row.expanded_workers_2010
        else:external[i]+=row.expanded_workers_2010
    commuting=ROOT/'sources'/'census_commuting_2022.json'
    local=municipal_series(commuting,12169);other=municipal_series(commuting,12188)
    home=municipal_series(commuting,12168);foreign=municipal_series(commuting,12189);multiple=municipal_series(commuting,12190)
    prior=np.zeros((n,n));diagonal=np.zeros(n,dtype=int);workers=np.zeros(n,dtype=int);audit=[]
    for i,code in enumerate(codes):
        universe=local[code]+other[code]+home[code]+foreign[code]+multiple[code]
        if universe<=0:raise ValueError('Empty Census commute universe')
        shares=matrix[i].copy();denominator=shares.sum()+external[i]
        if denominator<=0:raise ValueError('No historical destinations for '+code)
        shares/=denominator
        # A small explicit smoothing prior permits changes since 2010. It is not observed flow.
        smoothing=job_weights.copy();smoothing[i]=0;smoothing/=smoothing.sum()
        shares=(1-config['zero_pair_smoothing_share'])*shares+config['zero_pair_smoothing_share']*smoothing*(1-external[i]/denominator)
        destination_coverage=np.asarray([job_coverage.get(c,0) for c in codes])
        shares*=destination_coverage
        off=employed[i]*other[code]/universe*shares
        own=employed[i]*local[code]/universe*destination_coverage[i]
        diagonal[i]=round(own);workers[i]=diagonal[i]+round(off.sum())
        prior[i]=off;prior[i,i]=own
        audit.append({'municipality_code':code,'employed_pnad_calibrated':int(employed[i]),
            'census_2022_local_outside_home':local[code],'census_2022_other_municipality':other[code],
            'census_2022_home_workers':home[code],'census_2022_foreign_or_multiple':foreign[code]+multiple[code],
            'modeled_in_map_commuters':int(workers[i]),'excluded_home_external_multiple_or_boundary':int(employed[i]-workers[i]),
            'local_target':int(diagonal[i]),'historical_external_destination_share_2010':external[i]/denominator,
            'destination_boundary_coverage_proxy':float(destination_coverage[i])})
    off_rows=workers-diagonal
    initial_jobs=integer_totals(job_weights,int(workers.sum()))
    jobs=bounded_jobs(initial_jobs,diagonal,off_rows)
    rows,cols=np.where(~np.eye(n,dtype=bool))
    seed=prior[rows,cols];seed=np.maximum(seed,1e-12)
    fitted=fit_sparse(rows,cols,seed,off_rows,jobs-diagonal)
    values=round_transport(rows,cols,fitted,off_rows,jobs-diagonal)
    od=np.diag(diagonal);od[rows,cols]=values
    records=[]
    historic={(r.origin,r.destination):r.expanded_workers_2010 for r in history.itertuples(index=False)}
    for i,origin in enumerate(codes):
        audit[i].update(raw_scaled_job_target=int(initial_jobs[i]),reconciled_job_target=int(jobs[i]),job_target_adjustment=int(jobs[i]-initial_jobs[i]))
        for j,destination in enumerate(codes):
            records.append({'origin':origin,'destination':destination,'observed_2010_expanded':historic.get((origin,destination),0.),
                'observed_2022_pair':None,'seed_from_2022_containment_2010_shares':float(prior[i,j]),
                'balanced_target':int(od[i,j]),'change_from_seed':float(od[i,j]-prior[i,j]),
                'status':'2022 local containment' if i==j else 'historical 2010 survey prior, adjusted to modeled margins'})
    pd.DataFrame(records).to_csv(reports/'od_municipal_targets.csv',index=False)
    pd.DataFrame(audit).to_csv(reports/'commuter_universe.csv',index=False)
    return workers,jobs,od
