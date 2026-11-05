#!/usr/bin/env python3
"""Convert embedded PNG/JPEGs to high-quality lossy WebP without resizing.
Original HTML and image bytes are retained in the required --backup-dir.
"""
import argparse,base64,hashlib,io,json,math,re
from pathlib import Path
from PIL import Image,ImageChops,ImageStat

PATTERN=re.compile(r'data:image/(?:png|jpeg|jpg);base64,[A-Za-z0-9+/=]+')
def optimize(path,backup_dir,quality=92):
    source=path.read_text();backup_dir.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(source.encode()).hexdigest()
    backup=backup_dir/('index-'+digest[:16]+'.html')
    if not backup.exists():backup.write_text(source)
    replacements={};report=[]
    for match in PATTERN.finditer(source):
        url=match.group()
        if url in replacements:continue
        raw=base64.b64decode(url.split(',',1)[1],validate=True)
        key=hashlib.sha256(raw).hexdigest();ext='png' if url.startswith('data:image/png;') else 'jpg'
        original=backup_dir/(key+'.'+ext)
        if not original.exists():original.write_bytes(raw)
        with Image.open(io.BytesIO(raw)) as img:
            img.load();out=io.BytesIO()
            kwargs={k:img.info[k] for k in ('icc_profile','exif','xmp') if k in img.info}
            img.save(out,'WEBP',quality=quality,method=6,lossless=False,exact=True,**kwargs)
            encoded=out.getvalue()
            with Image.open(io.BytesIO(encoded)) as check:
                check.load();assert check.format=='WEBP' and check.size==img.size
                alpha_a=img.convert('RGBA').getchannel('A');alpha_b=check.convert('RGBA').getchannel('A')
                assert ImageChops.difference(alpha_a,alpha_b).getbbox() is None,'Alpha changed'
                rms=ImageStat.Stat(ImageChops.difference(img.convert('RGB'),check.convert('RGB'))).rms
                mse=sum(v*v for v in rms)/3
                psnr=round(10*math.log10(255**2/mse),2) if mse else None
            replacements[url]='data:image/webp;base64,'+base64.b64encode(encoded).decode()
            report.append(dict(original=key,dimensions=img.size,before=len(raw),after=len(encoded),psnr_db=psnr))
    result=PATTERN.sub(lambda m:replacements[m.group()],source)
    path.write_text(result)
    summary=dict(quality=quality,unique_images=len(report),occurrences=len(list(PATTERN.finditer(source))),html_before=len(source.encode()),html_after=len(result.encode()),images=report)
    (backup_dir/'webp-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='images'}))
    return summary
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--html',type=Path,default=Path('index.html'));ap.add_argument('--backup-dir',type=Path,required=True);ap.add_argument('--quality',type=int,default=92)
    args=ap.parse_args();assert 1<=args.quality<=100
    optimize(args.html,args.backup_dir,args.quality)
