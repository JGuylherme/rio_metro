"""Inspect the expanded scenery and census demand (not an in-game screenshot)."""
import json,pickle,os
os.environ.setdefault("MPLCONFIGDIR",str(__import__("pathlib").Path(__file__).resolve().parent/"data/matplotlib"))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection,PatchCollection
from matplotlib.patches import PathPatch,Rectangle
from matplotlib.path import Path
from shapely.geometry import shape
from map_settings import ROOT,DATA,OUT,PLAY_BBOX,VISUAL_BBOX


def patches(g):
    if g.geom_type=='Polygon':
        vertices=[];codes=[]
        for ring in [g.exterior,*g.interiors]:
            coords=list(ring.coords);vertices.extend(coords)
            codes.extend([Path.MOVETO]+[Path.LINETO]*(len(coords)-2)+[Path.CLOSEPOLY])
        yield PathPatch(Path(vertices,codes))
    elif hasattr(g,'geoms'):
        for child in g.geoms:yield from patches(child)


def main():
    surfaces=pickle.loads((DATA/'render_surfaces.pkl').read_bytes()) if (DATA/'render_surfaces.pkl').exists() else pickle.loads((DATA/'geography.pkl').read_bytes())[0]
    fig,ax=plt.subplots(figsize=(17,11),facecolor='#11202a');ax.set_facecolor('#e8e6df')
    for category,color in [('park','#b8c8ae'),('aerodrome','#ddd9d0'),('commercial','#dcc9b8'),('industrial','#c7c5be'),('water','#9fbfcb')]:
        polys=[]
        for layer,f in surfaces:
            match=(layer=='landuse' and f['properties'].get('kind')==category) or layer==category
            if match:polys.extend(patches(shape(f['geometry'])))
        ax.add_collection(PatchCollection(polys,facecolor=color,edgecolor='none'))
    p=DATA/'visual_roads.geojson'
    roads=json.loads((p if p.exists() else OUT/'roads.geojson').read_text())['features']
    for cls,color,width in [('minor','#b8bdbb',.13),('major','#fffaf0',.45),('highway','#d8a44c',.85)]:
        ax.add_collection(LineCollection([f['geometry']['coordinates'] for f in roads if f['properties']['roadClass']==cls],colors=color,linewidths=width))
    demand=json.loads((OUT/'demand_data.json').read_text())['points']
    for prefix,color,label in [('RES','#cf634d','Residentes · Censo 2022'),('WRK','#bc9634','Empregos · RAIS/CNEFE + informalidade modelada')]:
        selected=[p for p in demand if p['id'].startswith(prefix)]
        ax.scatter([p['location'][0] for p in selected],[p['location'][1] for p in selected],s=[min(120,max(2,(p['residents'] or p['jobs'])/700)) for p in selected],color=color,alpha=.65,linewidths=0,label=label)
    w,s,e,n=PLAY_BBOX
    ax.add_patch(Rectangle((w,s),e-w,n-s,fill=False,edgecolor='#325c80',linewidth=1.4,linestyle='--'))
    for name,x,y in [('JAPERI',-43.654,-22.636),('NOVA IGUAÇU',-43.451,-22.756),('RIO DE JANEIRO',-43.202,-22.908),('NITERÓI',-43.109,-22.905),('SÃO GONÇALO',-43.004,-22.828),('CAMPO GRANDE',-43.559,-22.908),('SANTA CRUZ',-43.685,-22.926)]:
        ax.text(x,y,name,fontsize=8,weight='bold',bbox={'facecolor':'white','edgecolor':'none','alpha':.8,'pad':2},color='#1d3544')
    ax.set_xlim(VISUAL_BBOX[0],VISUAL_BBOX[2]);ax.set_ylim(VISUAL_BBOX[1],VISUAL_BBOX[3]);ax.set_aspect(1.085)
    ax.tick_params(colors='#cbdce6');ax.spines[['top','right','bottom','left']].set_visible(False)
    ax.legend(loc='lower right',fontsize=8,framealpha=.95,markerscale=.5)
    fig.text(.075,.95,'GRANDE RIO • ATÉ JAPERI',fontsize=23,color='white',weight='bold')
    fig.text(.075,.916,'Linha tracejada: área de demanda. O cenário continua além do limite.',fontsize=11,color='#c1d1dc')
    fig.text(.075,.035,'Prévia dos dados. IBGE Censo 2022 · © OpenStreetMap contributors / Overture · GMRT',fontsize=10,color='#c1d1dc')
    fig.savefig(ROOT/'preview.png',dpi=160,bbox_inches='tight',facecolor=fig.get_facecolor())


if __name__=='__main__':main()
