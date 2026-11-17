"""Render a chuck from a SolidWorks eDrawings part (.eprt) as top / bottom view images and
embed them as the chuck overlay of one or more quiver-map HTML files.

usage: python3 chuck_overlay.py <chuck.eprt> <outdir> [map1.html map2.html ...]

The .eprt is a zip whose 'eModel' entry is a zlib-compressed HOOPS (HSF) stream. Each face
is a shell: float32 points (metres) followed by a byte/uint16 list of triangle strips.
Views are drawn with the painter's algorithm by height (strip winding is not consistent,
so no back-face culling). Bottom view is seen from below, i.e. mirrored in X."""
import re,struct,zlib,zipfile,sys,io,base64,json,numpy as np
from PIL import Image, ImageDraw, ImageFilter
src,outdir=sys.argv[1],sys.argv[2]
import os; os.makedirs(outdir,exist_ok=True)
z=zipfile.ZipFile(src); d=z.read('eModel'); r=zlib.decompressobj().decompress(d[d.find(b'\x78\xda'):])
tris=[]; nf=0
for m in re.finditer(rb'swfaceid=(\d+)\x00',r):
    q=r.find(b'S',m.end(),m.end()+8)
    if q<0 or r[q+1]!=0x0e: continue
    cnt=struct.unpack('<i',r[q+7:q+11])[0]; e=q+11+cnt*12; w=r[e+5]; L=struct.unpack('<i',r[e+1:e+5])[0]
    P=np.frombuffer(r[q+11:e],dtype='<f4').reshape(-1,3).astype(float)*1e3
    ne=(L-1)//(w//8)
    v=list(r[e+6:e+6+ne]) if w==8 else list(struct.unpack(f'<{ne}H',r[e+6:e+6+2*ne]))
    i=0
    while i<len(v):
        n=v[i]
        if n<3 or i+1+n>len(v) or max(v[i+1:i+1+n])>=cnt: break
        s=v[i+1:i+1+n]
        for k in range(n-2): tris.append(np.r_[P[s[k]],P[s[k+1]],P[s[k+2]]])
        i+=1+n
    nf+=1
T=np.array(tris); A,B,C=T[:,0:3],T[:,3:6],T[:,6:9]
n=np.cross(B-A,C-A); ny=n[:,1]/(np.linalg.norm(n,axis=1)+1e-12); ym=(A[:,1]+B[:,1]+C[:,1])/3
ytop=ym.max(); ybot=ym.min()
print('faces',nf,'triangles',len(T),'height',round(ybot,2),'..',round(ytop,2))
S=1400; R=155.0; sc=S/(2*R)
def render(view):
    up = np.abs(ny)>0.3   # strip winding in the file is not consistent -> no culling; painter's order by height instead
    idx=np.where(up)[0]; idx=idx[np.argsort(ym[idx])] if view=='top' else idx[np.argsort(-ym[idx])]
    im=Image.new('RGBA',(S,S),(0,0,0,0)); dr=ImageDraw.Draw(im)
    rr=153*sc; dr.ellipse([S/2-rr,S/2-rr,S/2+rr,S/2+rr],fill=(45,48,56,255))   # through-holes show dark
    for t in idx:
        depth=(ytop-ym[t]) if view=='top' else (ym[t]-ybot)                   # distance below the viewed surface
        g=int(max(70,min(222,222-depth*10-(40 if depth>0.05 else 0))))
        sx=-1 if view=='bottom' else 1                                            # seen from below = mirrored in X
        pts=[(S/2+sx*T[t,j]*sc,S/2+T[t,j+2]*sc) for j in (0,3,6)]
        dr.polygon(pts,fill=(g,g,g,255))
    im=im.filter(ImageFilter.SMOOTH)
    b=io.BytesIO(); im.convert('LA').save(b,'PNG',optimize=True); im.save(f'{outdir}/chuck_{view}.png')
    return base64.b64encode(b.getvalue()).decode()
out={'R':R,'top':render('top'),'bottom':render('bottom')}
json.dump(out,open(f'{outdir}/chuck_imgs.json','w'))
print('png sizes kB: top',len(out['top'])*3//4//1024,'bottom',len(out['bottom'])*3//4//1024)

for html in sys.argv[3:]:
    s=open(html,encoding='utf-8').read()
    blk='<script id="chuck" type="application/json">'+json.dumps(out,separators=(',',':'))+'</script>'
    s,n=re.subn(r'<script id="chuck" type="application/json">.*?</script>',lambda m:blk,s,count=1,flags=re.S)
    if n!=1: print('no chuck block in',html,'(build it from a v2.1+ template)'); continue
    open(html,'w',encoding='utf-8').write(s); print('chuck overlay updated in',html)
