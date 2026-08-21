from itertools import permutations
# events: ('K',i) kill-side step i ; ('A',i) arm-side step i
def run(order, arm_stores_first):
    st={'killed':0,'ready':0}; K={}; A={}
    for who,i in order:
        if who=='K':
            if i==0: st['killed']=1
            else: K['ready']=st['ready']
        else:
            if arm_stores_first:
                if i==0: st['ready']=1
                else: A['killed']=st['killed']
            else:
                if i==0: A['killed']=st['killed']
                else: st['ready']=1
    kill_kills = K.get('ready',0)==1
    arm_kills  = A.get('killed',0)==1
    return kill_kills or arm_kills
def enum(arm_stores_first):
    evs=[('K',0),('K',1),('A',0),('A',1)]
    seen=set(); lost=[]; tot=0
    for p in permutations(evs):
        # keep program order per side
        if p.index(('K',0))>p.index(('K',1)): continue
        if p.index(('A',0))>p.index(('A',1)): continue
        tot+=1
        if not run(p, arm_stores_first): lost.append(p)
    return tot,lost
for label,f in (("AS WRITTEN (arm: LD killed, ST ready)",False),("FIXED (arm: ST ready, LD killed)",True)):
    tot,lost=enum(f)
    print(f"{label}: {tot} interleavings, {len(lost)} lose the kill")
    for l in lost: print("   witness:", " / ".join(f"{w}{i}" for w,i in l))
