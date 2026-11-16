import openpyxl, json, math, sys, re
src, tpl, out = sys.argv[1], sys.argv[2], sys.argv[3]
wb=openpyxl.load_workbook(src,read_only=True,data_only=True)
def sheet(name):
    rows=list(wb[name].iter_rows(values_only=True))
    hdr, tim = rows[0], rows[1]
    runs=[str(h) for h in hdr[2:] if h is not None]
    times=[str(t) for t in tim[2:2+len(runs)]]
    pts=[];vals=[]
    for r in rows[2:]:
        if r[0] is None or r[1] is None: continue
        pts.append((float(r[0]),float(r[1]))); vals.append([None if v is None or v=='' else float(v) for v in r[2:2+len(runs)]])
    return runs,times,pts,vals
rx,tx,px,X=sheet('ShiftX'); ry,ty,py,Y=sheet('ShiftY'); rm,tm,pm,M=sheet('Magnitude')
assert rx==ry==rm and px==py==pm and tx==ty==tm, 'sheet layout mismatch'
# verify magnitude
mx=0; nchk=0; miss=0; inconsistent=0
for i in range(len(px)):
    for t in range(len(rx)):
        a,b,m=X[i][t],Y[i][t],M[i][t]
        if a is None or b is None:
            miss+=1
            if (a is None)!=(b is None) or m is not None: inconsistent+=1
            continue
        if m is None: inconsistent+=1; continue
        mx=max(mx,abs(math.hypot(a,b)-m)); nchk+=1
print(f'dies {len(px)}, scans {len(rx)}, runs {rx[0]}..{rx[-1]}, time {tx[0]} -> {tx[-1]}')
print(f'magnitude check: {nchk} values, max |sqrt(X²+Y²)-Mag| = {mx:.2e}; missing cells {miss}; inconsistent {inconsistent}')
gaps=[int(b)-int(a) for a,b in zip(rx,rx[1:]) if a.isdigit() and b.isdigit()]
print('run-number gaps >1:', sum(g>1 for g in gaps))
r4=lambda v: None if v is None else round(v,4)
data={'runs':rx,'times':tx,'pts':[[round(a,1),round(b,1)] for a,b in px],'dx':[[r4(v) for v in row] for row in X],'dy':[[r4(v) for v in row] for row in Y]}
js=json.dumps(data,separators=(',',':'))
html=open(tpl,encoding='utf-8').read()
html,n=re.subn(r'(<script id="data" type="application/json">).*?(</script>)',lambda m:m.group(1)+js+m.group(2),html,count=1,flags=re.S)
assert n==1
open(out,'w',encoding='utf-8').write(html); print('written',out,len(html))
