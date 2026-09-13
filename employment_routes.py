"""Extend the demand routing support with real shortest paths to employment areas."""
import hashlib,json,pickle,math
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components,dijkstra
from scipy.spatial import cKDTree
from map_settings import DATA
from geography import PROJECT


def expand(points,routes,workers,groups,targets):
    signature=hashlib.sha256(json.dumps([(p['id'],p['location']) for p in points]).encode()+groups.tobytes()+targets.tobytes()).hexdigest()
    path=DATA/'employment_route_pool.pkl'
    if path.exists():
        cached=pickle.loads(path.read_bytes())
        if cached['signature']==signature:return cached['routes']
    print('Extending actual road routes to employment areas',flush=True)
    _,_,edges,nodes=pickle.loads((DATA/'geography.pkl').read_bytes())
    ids=sorted({e[0] for e in edges}|{e[1] for e in edges});idx={n:i for i,n in enumerate(ids)};pairs={}
    for a,b,length,secs,direction in edges:
        arcs=[(b,a)] if direction=='-1' else [(a,b)] if direction in {'yes','1','true'} else [(a,b),(b,a)]
        for a,b in arcs:
            key=(idx[a],idx[b])
            if key not in pairs or secs<pairs[key]:pairs[key]=secs
    rows,cols=zip(*pairs);graph=coo_matrix((list(pairs.values()),(rows,cols)),shape=(len(ids),len(ids))).tocsr()
    _,comp=connected_components(graph,directed=True,connection='strong');keep=np.flatnonzero(comp==np.bincount(comp).argmax())
    graph=graph[keep][:,keep].T.tocsr()
    pos=np.array([nodes[ids[i]] for i in keep]);xy=np.column_stack(PROJECT(pos[:,0],pos[:,1]))
    loc=np.array([p['location'] for p in points]);pxy=np.column_stack(PROJECT(loc[:,0],loc[:,1]))
    _,snap=cKDTree(xy).query(pxy)
    homes=np.flatnonzero(workers>0);rng=np.random.default_rng(20260911)
    existing={(p['residenceId'],p['jobId']) for p in routes};output=list(routes)
    for g,target in enumerate(targets):
        if target<=0:continue
        sites=np.flatnonzero(groups==g)
        jobs=[int(i) for i in sites if points[i]['residents']==0]
        candidates=np.array(jobs if jobs else sites)
        # Spread added routes across up to four real existing anchors.
        chosen=[int(candidates[0])]
        while len(chosen)<min(4,len(candidates)):
            distances=np.min(np.linalg.norm(pxy[candidates,None]-pxy[chosen],axis=2),axis=1)
            chosen.append(int(candidates[np.argmax(distances)]))
        for dest in chosen:
            distance=np.linalg.norm(pxy[homes]-pxy[dest],axis=1)
            nearest=homes[np.argsort(distance)[:96]]
            probability=np.exp(-distance/25000)*workers[homes];probability/=probability.sum()
            sampled=rng.choice(homes,size=min(128,len(homes)),replace=False,p=probability)
            selected=np.unique(np.concatenate([nearest,sampled]))
            # Large job centers must be reachable from enough residents to meet quotas.
            needed=target*2/len(chosen)
            if workers[selected].sum()<needed:
                order=homes[np.argsort(distance)]
                count=np.searchsorted(np.cumsum(workers[order]),needed)+1
                selected=np.unique(np.concatenate([selected,order[:count]]))
            times,pred=dijkstra(graph,directed=True,indices=int(snap[dest]),return_predecessors=True)
            for origin in selected:
                if origin==dest or (points[origin]['id'],points[dest]['id']) in existing:continue
                cursor=int(snap[origin]);length=0.
                while cursor!=snap[dest]:
                    previous=int(pred[cursor])
                    if previous<0:raise RuntimeError('Disconnected job route')
                    length+=math.dist(xy[cursor],xy[previous]);cursor=previous
                p={'id':str(len(output)),'residenceId':points[origin]['id'],'jobId':points[dest]['id'],'size':0,
                    'drivingDistance':max(1,round(length)),'drivingSeconds':max(1,round(times[snap[origin]]))}
                output.append(p);existing.add((p['residenceId'],p['jobId']))
        if g%10==0:print('Employment regions routed',g+1,'/',len(targets),'routes',len(output),flush=True)
    path.write_bytes(pickle.dumps({'signature':signature,'routes':output},protocol=5))
    return output
