"""Conditional rubric scenarios, never a maintainer-confirmed tier."""
import json
from map_settings import ROOT


def scenario(name,wg,wr,wi,rg,rr,ri,od):
    w=(.5*.7+.5*wr*wi)*wg
    r=(.5*.7+.5*rr*ri)*rg
    score=.5*w+.35*r+.15*od
    return {'scenario':name,'workplace':w,'resident':r,'od':od,'composite':score,
        'conditional_tier':'high' if score>=.60 else 'medium' if score>=.45 else 'low',
        'reviewed':False}


def main():
    rows=[scenario('Conservative placement and municipal fallback; OD discounted to marginal',.7,.7,.85,.95,.7,1,.5*.7),
          scenario('Municipal workplace grain; measured census-unit residence; historical sampled OD accepted',.7,.7,.85,.95,.9,1,.75*.7),
          scenario('Submunicipal workplace grain accepted; OD discounted to marginal',.9,.7,.85,.95,.9,1,.5*.7),
          scenario('Submunicipal workplace grain and historical sampled OD accepted',.9,.7,.85,.95,.9,1,.75*.7)]
    output={'official_previous_reviewed_composite':.33,'rubric_url':'https://github.com/Subway-Builder-Modded/registry/blob/main/docs/data-quality.md',
        'formula':'W/R=(0.5*count+0.5*resolution*intensity)*grain; composite=0.5W+0.35R+0.15OD',
        'qualification':'Scenario analysis, not a prediction or submitted review. Unknown business activity, informal placement, broad CEPs and historical OD can receive lower classifications.',
        'scenarios':rows}
    (ROOT/'reports/quality/score_scenarios.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
