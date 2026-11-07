"""One closed A2 intervention; no external Python or tunable expression is executed."""
import math

MECHANISM = 'airfoil-suction-strouhal-v1'
SOURCE = 'def augment(row):\n    return row + [row[0] * row[4] / row[3]]\n'


def augment(row):
    if (not isinstance(row,list) or len(row)!=5 or
            any(type(x) not in (int,float) or not math.isfinite(x) for x in row) or
            any(row[i]<=0 for i in (0,2,3,4)) or row[1]<0):
        raise ValueError('Expected five finite physical inputs with positive frequency/length/speed/thickness')
    value=row[0]*row[4]/row[3]
    if not math.isfinite(value): raise ValueError('Nonfinite Strouhal feature')
    return row+[value]


def review(source=SOURCE):
    if source!=SOURCE: raise ValueError('Only the exact frozen Strouhal intervention is supported; no constants or alternatives')
    # Synthetic grid: hold each original coordinate fixed while the new value varies.
    rows=[[f,a,c,u,d] for f in (500.,2000.) for a in (0.,5.) for c in (.1,.3)
          for u in (30.,60.) for d in (.002,.008)]
    values=[augment(r)[-1] for r in rows]
    if len(set(values))<2: raise ValueError('Constant intervention')
    for j in range(5):
        groups={}
        for r,v in zip(rows,values): groups.setdefault(r[j],set()).add(v)
        if all(len(g)==1 for g in groups.values()): raise ValueError('Redundant single-column intervention')
    if augment([1000.,0.,.1,50.,.005])[-1] != .1: raise ValueError('Formula check failed')
    return {'mechanism':MECHANISM,'appended_columns':1,'effective_input_columns':[0,3,4],
            'synthetic_probe_passed':True,'original_columns_unchanged':True,
            'limit':'Rejects this fixed feature as a constant/single-column duplicate; not a general semantic novelty proof'}
