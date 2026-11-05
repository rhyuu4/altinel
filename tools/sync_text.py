#!/usr/bin/env python3
"""Import Altinel editorial workbooks without running VBA. Requires openpyxl and Node.js."""
import argparse, html, json, re, subprocess, tempfile
from pathlib import Path
from html.parser import HTMLParser
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Protection

class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source=source; self.lines=[0]; self.nodes=[]; self.stack=[]; self.texts=[]
        self.lines += [m.end() for m in re.finditer('\n',source)]
        self.feed(source)
    def position(self):
        r,c=self.getpos(); return self.lines[r-1]+c
    def handle_starttag(self,tag,attrs):
        parent=self.stack[-1] if self.stack else None
        siblings=[n for n in self.nodes if n['parent'] is parent and n['tag']==tag]
        path=(parent['path'] if parent else '')+'/'+tag+'['+str(len(siblings)+1)+']'
        start=self.position(); node=dict(tag=tag,attrs=dict(attrs),parent=parent,path=path,start=start,inner=start+len(self.get_starttag_text()),end=None)
        self.nodes.append(node)
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'): self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]['tag']==tag:
                self.stack[i]['end']=self.position(); self.stack=self.stack[:i]; break
    def handle_data(self,data):
        if self.stack:
            n=self.stack[-1]; self.texts.append(dict(node=n,start=self.position(),end=self.position()+len(data),value=data))
    def handle_entityref(self,name): self.handle_data('&'+name+';')
    def handle_charref(self,name): self.handle_data('&#'+name+';')
    def find(self,tag=None,ident=None,cls=None):
        return next(n for n in self.nodes if (not tag or n['tag']==tag) and (not ident or n['attrs'].get('id')==ident) and (not cls or cls in n['attrs'].get('class','').split()))

def apply(source, edits):
    for a,b,value in sorted(edits,reverse=True): source=source[:a]+value+source[b:]
    return source

def text(value):
    if value is None:return ''
    if isinstance(value,float) and value.is_integer():return str(int(value))
    return str(value)
def quote(value): return json.dumps(value,ensure_ascii=False).replace('</','<\\/')
def identifier(value):
    v=text(value); return v.zfill(2) if v.isdigit() else v

def data_from(source):
    script=re.findall(r'<script>(.*?)</script>',source,re.S)[0]
    code=script+'\nconsole.log(JSON.stringify({data:ALTINEL_DATA,combat:ALTINEL_COMBAT}));'
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'extract.cjs';p.write_text(code)
        return json.loads(subprocess.check_output(['node',str(p)]))

def import_core(source,wb):
    bundle=data_from(source); data=bundle['data']; combat=bundle['combat']
    cast_sheet=next(n for n in wb.sheetnames if n.startswith('등장인물 '))
    combat_sheet=next(n for n in wb.sheetnames if n.startswith('전투 능력 '))
    cast_rows=[r for r in wb[cast_sheet].iter_rows(min_row=5,max_col=10,values_only=True) if r[0] is not None]
    desired=[identifier(r[0]) for r in cast_rows]
    if [p['id'] for p in data['cast']]!=desired:
        assert '인물 ID 대응' in wb,'Renumbering requires the image ID mapping sheet'
        mapping={identifier(r[0]):identifier(r[1]) if r[1] is not None else None for r in wb['인물 ID 대응'].iter_rows(min_row=2,max_col=4,values_only=True) if r[0] is not None}
        old={p['id']:p for p in data['cast']}; rebuilt=[]
        for ident in desired:
            prior=mapping[ident]
            assert prior is None or prior in old,'Unknown previous image ID'
            item=dict(old[prior]) if prior else {'indexImage':'','image':'','chatUrl':''}
            item['id']=ident;rebuilt.append(item)
        data['cast']=rebuilt
    for sheet,group,fields in [(cast_sheet,'cast',['shortName','name','group','faction','nation','role','personality','tagline','description']),('보스 4명','bosses',['title','name','faction','nation','role','personality','tagline','description'])]:
        rows=list(wb[sheet].iter_rows(min_row=5,values_only=True)); byid={identifier(r[0]):r for r in rows if r[0] is not None}
        assert set(byid)=={x['id'] for x in data[group]},sheet+' ID mismatch'
        for item in data[group]:
            for field,value in zip(fields,byid[item['id']][1:]): item[field]=text(value)
            item.pop('combat',None)
    combat={}
    for row in wb[combat_sheet].iter_rows(min_row=5,max_col=9,values_only=True):
        if row[0] is not None:
            key=identifier(row[0]); assert key in {p['id'] for p in data['cast']+data['bosses']}
            combat[key]={k:text(v) for k,v in zip(['circle','divine','martial','rank','implant','secretImplant','specialty'],row[2:9])}
    assert set(combat)=={p['id'] for p in data['cast']+data['bosses']},'Combat IDs do not match roster'
    rows=[r for r in wb['대륙과 국가'].iter_rows(min_row=5,values_only=True) if any(v is not None for v in r)]
    assert len(rows)==6
    for i,c in enumerate(data['continents']):
        pair=rows[i*2:i*2+2]; assert tuple(pair[0][:3])==tuple(pair[1][:3]),'대륙 공통 설정의 두 행이 다릅니다'
        c.update(faction=text(pair[0][0]),orientation=text(pair[0][1]),summary=text(pair[0][2]))
        c['nations']=[dict(zip(['name','city','text'],map(text,r[3:6]))) for r in pair]
    source=re.sub(r'const ALTINEL_DATA = .*?;\s*/\*',lambda _: 'const ALTINEL_DATA = '+quote(data)+';\n\n/*',source,count=1,flags=re.S)
    source=re.sub(r'const ALTINEL_COMBAT = .*?;\s*ALTINEL_DATA.cast',lambda _: 'const ALTINEL_COMBAT = '+quote(combat)+';\nALTINEL_DATA.cast',source,count=1,flags=re.S)
    values={text(r[0]):text(r[2]) for r in wb['홈페이지 문구'].iter_rows(min_row=5,values_only=True) if r[0]}
    doc=Document(source); edits=[]; covered=set()
    def inner(node,value):
        edits.append((node['inner'],node['end'],value));covered.add(node['path'])
    def val(key): return html.escape(values[key]).replace('\n','<br>')
    inner(doc.find(cls='hero-eyebrow'),val('heroEyebrow'))
    inner(doc.find(ident='hero-title'),val('heroTitleLine1')+'<br>'+val('heroTitleLine2')+'<br><em>'+val('heroTitleAccent')+'</em>')
    inner(doc.find(cls='hero-sub'),val('heroDesc'))
    for key,ident in [('academyTitle','academy-title'),('rosterTitle','roster-title'),('bossTitle','targets-title'),('worldTitle','setting-title'),('closingButton','site-chat-link')]: inner(doc.find(ident=ident),val(key))
    for key,ident in [('academySubtitle','academy-title'),('rosterSubtitle','roster-title'),('bossSubtitle','targets-title'),('worldSubtitle','setting-title')]:
        title=doc.find(ident=ident)
        node=next(n for n in doc.nodes if n['parent'] is title['parent'] and n['tag']=='p' and n['start']>title['end'])
        inner(node,val(key))
    intro=doc.find(cls='academy-intro-copy')
    for key,tag in [('academyIntroTitle','strong'),('academyIntroText','p')]:inner(next(n for n in doc.nodes if n['parent'] is intro and n['tag']==tag),val(key))
    closing=doc.find(cls='closing-content')
    for key,tag in [('closingTitle','h2'),('closingSubtitle','p')]:
        inner(next(n for n in doc.nodes if n['parent'] is closing and n['tag']==tag and (tag!='p' or not n['attrs'].get('class'))),val(key))
    tables=[n for n in doc.nodes if n['tag']=='tbody']; assert len(tables)==2
    schedule=list(wb['학사일정'].iter_rows(min_row=5,max_col=5,values_only=True))
    for i,table in enumerate(tables):
        trs=[]
        for term,date,event,note,style in schedule:
            if text(term)!=str(i+1)+'학기':continue
            klass={'일반':'','강조':'highlight-schedule','주의':'danger-schedule'}[style]
            trs.append('<tr'+(' class="'+klass+'"' if klass else '')+'><td>'+html.escape(text(date))+'</td><td>'+html.escape(text(event))+(' <span class="event-sub">'+html.escape(text(note))+'</span>' if note else '')+'</td></tr>')
        inner(table,'\n'+'\n'.join(trs)+'\n')
    return apply(source,edits),covered

# Runtime labels are shared across rendering, buttons, status messages and accessibility labels.
DYNAMIC={
 'reveal':('정체 공개','보스 / 정체 공개 버튼'), 'reseal':('다시 가리기','보스 / 개별 숨김 버튼'),
 'sealedDescription':('정체와 능력 정보가 보호되어 있습니다.','보스 / 봉인 상태 설명'),
 'sealedBadge':('SEALED','보스 / 봉인 배지'),'revealedBadge':('UNSEALED','보스 / 공개 배지'),
 'classified':('CLASSIFIED','보스 / 봉인 이미지 제목'),'identityProtected':('IDENTITY PROTECTED','보스 / 봉인 이미지 부제'),
 'bossDetail':('상세 능력 ↗','보스 / 상세 버튼'),'targetPrefix':('TARGET / ','보스 / 번호 접두사'),
 'filePrefix':('FILE / ','인물 / 번호 접두사'),'portraitPending':('PORTRAIT PENDING','인물 / 초상화 미등록'),
 'portraitWatermark':('ALTINEL','인물 / 대체 이미지 워터마크'),
 'emptyRoster':('선택한 분류에 해당하는 인물이 없습니다.','인물 / 결과 없음'),
 'emptyHelp':('역할이나 계열을 다른 항목으로 바꿔보세요.','인물 / 결과 없음 도움말'),
 'profilesSuffix':('PROFILES','인물 / 결과 수 단위'),
 'allFilter':('전체','인물 / 전체 필터'),
 'castDossier':('ALTINEL · CHARACTER DOSSIER','상세창 / 일반 인물 분류'),
 'bossDossier':('BOSS DOSSIER · REVEALED','상세창 / 보스 분류'),
 'bossGroup':('타도 대상','상세창 / 보스 소속'),
 'secretHidden':('이식 정보 비공개','상세창 / 비공개 이식 표시'),
 'spoilerOpen':('스포일러 열기','상세창 / 스포일러 버튼'), 'spoilerClose':('다시 숨기기','상세창 / 스포일러 닫기'),
 'chatReady':('외부 캐릭터채팅 사이트가 새 탭에서 열립니다.','하단 / 채팅 주소 등록 시 안내'),
 'chatPending':('채팅 페이지 주소 등록 예정','하단 / 채팅 주소 미등록 안내'),
 'chatToast':('아직 채팅 사이트 주소가 등록되지 않았습니다.','알림 / 채팅 주소 미등록'),
 'resealToast':('보스 4명의 정보를 다시 가렸습니다.','알림 / 보스 전체 숨김'),
 'menuOpen':('메뉴 열기','접근성 / 메뉴 열기'), 'menuClose':('메뉴 닫기','접근성 / 메뉴 닫기'),
 'profileOpenSuffix':(' 상세 프로필 열기','접근성 / 인물 버튼 이름 접미사'),
 'portraitAltSuffix':(' 초상','접근성 / 초상화 대체 텍스트 접미사'),
 'emblemAltSuffix':(' 엠블럼','접근성 / 계열 문장 대체 텍스트 접미사'),
 'cityPrefix':('주요 거점 · ','세계 / 도시 접두사'),
 'missingValue':('—','상세창 / 미기재 표시'),
}

def bind_dynamic(source):
    if 'const ALTINEL_UI =' in source:return source
    ui={k:v[0] for k,v in DYNAMIC.items()}
    marker="document.addEventListener('DOMContentLoaded', () => {"
    source=source.replace(marker,'const ALTINEL_UI = '+quote(ui)+';\n'+marker)
    start=source.index(marker);end=source.index('</script>',start);a=source[:start];b=source[start:end];tail=source[end:]
    # Quoted literals in the runtime script, longest first. Avoid changing selector attributes.
    for key,(value,_) in sorted(DYNAMIC.items(),key=lambda x:len(x[1][0]),reverse=True):
        for q in ("'",'"'):
            b=b.replace(q+value+q,'ALTINEL_UI.'+key)
    # HTML snippets inside strings must become template strings when introducing expressions.
    b=b.replace("'<div class=\"boss-lock\" aria-hidden=\"true\"><span>✦</span><strong>CLASSIFIED</strong><small>IDENTITY PROTECTED</small></div>'",'`<div class="boss-lock" aria-hidden="true"><span>✦</span><strong>${esc(ALTINEL_UI.classified)}</strong><small>${esc(ALTINEL_UI.identityProtected)}</small></div>`')
    b=b.replace("'<span class=\"roster-status\">PORTRAIT PENDING</span>'",'`<span class="roster-status">${esc(ALTINEL_UI.portraitPending)}</span>`')
    for old,new in [
      ('>ALTINEL</span>','>${esc(ALTINEL_UI.portraitWatermark)}</span>'),
      ('${esc(person.name)} 초상','${esc(person.name)}${esc(ALTINEL_UI.portraitAltSuffix)}'),
      ('${esc(ch.name)} 상세 프로필 열기','${esc(ch.name)}${esc(ALTINEL_UI.profileOpenSuffix)}'),
      ('FILE / ${esc(ch.id)}','${esc(ALTINEL_UI.filePrefix)}${esc(ch.id)}'),
      ('TARGET / ${String(i+1)','${esc(ALTINEL_UI.targetPrefix)}${String(i+1)'),
      ('${esc(continent.faction)} 엠블럼','${esc(continent.faction)}${esc(ALTINEL_UI.emblemAltSuffix)}'),
      ('주요 거점 · ${esc(nation.city)}','${esc(ALTINEL_UI.cityPrefix)}${esc(nation.city)}'),
      ('${data.cast.length} PROFILES','${data.cast.length} ${ALTINEL_UI.profilesSuffix}'),
      ('>상세 능력 ↗</button>','>${esc(ALTINEL_UI.bossDetail)}</button>'),
      ('선택한 분류에 해당하는 인물이 없습니다.<br>역할이나 계열을 다른 항목으로 바꿔보세요.','${esc(ALTINEL_UI.emptyRoster)}<br>${esc(ALTINEL_UI.emptyHelp)}')]: b=b.replace(old,new)
    b=b.replace('${revealed ? ALTINEL_UI.revealedBadge : ALTINEL_UI.sealedBadge}', '${esc(revealed ? ALTINEL_UI.revealedBadge : ALTINEL_UI.sealedBadge)}').replace('${revealed ? ALTINEL_UI.reseal : ALTINEL_UI.reveal}', '${esc(revealed ? ALTINEL_UI.reseal : ALTINEL_UI.reveal)}')
    return a+b+tail

def extra_rows(source,covered):
    doc=Document(source); rows=[]
    for n in doc.nodes:
        if n['end'] is None:continue
        if n['path'] in covered or any(n['path'].startswith(c+'/') for c in covered):continue
        if n['tag'] in ('script','style') or n['attrs'].get('id') in ('roster-count','dialog-type','dialog-name','site-chat-note','secret-combat-reveal'):continue
        # Include direct text runs as a unit; preserve inline elements and entities.
        runs=[t for t in doc.texts if t['node'] is n]
        groups=[]
        for t in runs:
            if groups and groups[-1][-1]['end']==t['start']:groups[-1].append(t)
            else:groups.append([t])
        for i,g in enumerate(groups):
            raw=''.join(t['value'] for t in g)
            if not html.unescape(raw).strip():continue
            if n['tag']=='tbody' or '/tbody[' in n['path']:continue
            if n['tag']=='title' or n['path'].startswith('/html[1]/body[1]'):
                # Decorative icons remain design assets.
                value=html.unescape(raw).strip()
                if not re.search(r'[\w가-힣]',value):continue
                context=n
                while context['parent'] and not context['attrs'].get('id') and context['tag'] not in ('header','footer','section'):context=context['parent']
                section=context['attrs'].get('id') or context['tag']
                rows.append(('text:'+n['path']+':'+str(i),section+' / '+(n['attrs'].get('id') or n['attrs'].get('class') or n['tag']),value,'정적 문구 / 해당 위치의 글만 변경'))
    for n in doc.nodes:
        for attr in ('aria-label','alt'):
            if attr in n['attrs']:rows.append(('attr:'+n['path']+':'+attr,'접근성 / '+(n['attrs'].get('id') or n['tag']),n['attrs'][attr],'접근성 설명'))
        if n['tag']=='meta' and n['attrs'].get('name')=='description':rows.append(('attr:'+n['path']+':content','검색 결과 / 사이트 설명',n['attrs']['content'],'검색엔진 요약'))
    rows.extend(('ui:'+k,desc,value,'동작 중 생성되는 문구') for k,(value,desc) in DYNAMIC.items())
    rows.append(('setting:siteChatUrl','하단 / 채팅 연결 주소',data_from(source)['data'].get('siteChatUrl',''),'https:// 주소, 비워 두면 미등록'))
    return rows

def import_extra(source,wb):
    if '기타 화면 문구' not in wb:return source
    doc=Document(source); bypath={n['path']:n for n in doc.nodes};edits=[];ui={};chat_url=None
    for key,location,value,note in wb['기타 화면 문구'].iter_rows(min_row=5,max_col=4,values_only=True):
        if not key:continue
        value=text(value)
        if key.startswith('ui:'):ui[key[3:]]=value;continue
        if key=='setting:siteChatUrl':
            assert not value or re.match(r'^https?://',value),'채팅 주소는 http(s) URL이어야 합니다'
            chat_url=value;continue
        kind,path,tail=key.split(':',2); n=bypath[path]
        if kind=='text':
            runs=[t for t in doc.texts if t['node'] is n];groups=[]
            for t in runs:
                if groups and groups[-1][-1]['end']==t['start']:groups[-1].append(t)
                else:groups.append([t])
            g=groups[int(tail)];raw=source[g[0]['start']:g[-1]['end']]
            lead=re.match(r'^\s*',raw)[0];trail=re.search(r'\s*$',raw)[0]
            edits.append((g[0]['start'],g[-1]['end'],lead+html.escape(value)+trail))
        else:
            raw=source[n['start']:n['inner']];m=re.search(r'\b'+re.escape(tail)+r'\s*=\s*([\"\'])(.*?)\1',raw,re.S);assert m,key
            edits.append((n['start']+m.start(2),n['start']+m.end(2),html.escape(value,quote=True)))
    # Apply offsets before changing script lengths.
    source=apply(source,edits)
    if chat_url is not None:source=re.sub(r'ALTINEL_DATA.siteChatUrl = .*?;',lambda _: 'ALTINEL_DATA.siteChatUrl = '+quote(chat_url)+';',source,count=1)
    if ui:
        source=re.sub(r'const ALTINEL_UI = .*?;\n',lambda _: 'const ALTINEL_UI = '+quote(ui)+';\n',source,count=1)
    return source

def extend_workbook(wb,source,covered):
    if '기타 화면 문구' in wb:return
    sheet=wb.create_sheet('기타 화면 문구')
    sheet.append(['ADDITIONAL SITE COPY · 안내·버튼·메뉴·상세창'])
    sheet.append(['C열 노란색 칸만 수정하세요. ID는 변경하지 마세요. 기존 시트에 없는 정적 문구·동적 문구·접근성 설명입니다. 매크로 실행은 필요 없습니다.'])
    sheet.append([]);sheet.append(['문구 ID(고정)','적용 위치','현재 문구(여기 수정)','비고'])
    for row in extra_rows(source,covered):sheet.append(row)
    for row in sheet.iter_rows(min_row=5):
        for c in row:c.alignment=Alignment(vertical='top',wrap_text=True)
        row[0].fill=PatternFill('solid',fgColor='DCEAF7');row[0].font=Font(color='244062')
        row[2].fill=PatternFill('solid',fgColor='FFF2CC');row[2].protection=Protection(locked=False)
        sheet.row_dimensions[row[0].row].height=34
    for c in sheet[4]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='24354B')
    for col,width in [('A',65),('B',32),('C',90),('D',42)]:sheet.column_dimensions[col].width=width
    sheet.freeze_panes='C5';sheet.auto_filter.ref=f'A4:D{sheet.max_row}'
    usage=wb['사용 방법'];usage['A1']='아카데미 알티넬 · 텍스트 편집 자료집 V10 확장판'
    usage['D9']=str(wb['홈페이지 문구'].max_row-4)+'개'
    usage['A10']='07';usage['B10']='기타 화면 문구';usage['C10']='스포일러 안내, 공개·숨김 버튼, 메뉴, 상세창, 알림, 검색·접근성 문구';usage['D10']=str(sheet.max_row-4)+'개'
    usage['A16']='• 저장한 파일을 채팅에 업로드하면 현재 홈페이지에 반영합니다. 이미지·디자인은 유지합니다.'
    usage['A19']='• 기타 화면 문구의 C열도 수정할 수 있습니다. ID와 적용 위치는 수정하지 마세요. 매크로 실행은 필요 없습니다.'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('workbook');ap.add_argument('--html',default='index.html');ap.add_argument('--export-workbook');args=ap.parse_args()
    p=Path(args.html);before=p.read_text();wb=openpyxl.load_workbook(args.workbook,keep_vba=True)
    after,covered=import_core(before,wb);after=bind_dynamic(after);after=import_extra(after,wb)
    before_images=re.findall(r'data:image/[^\s\"\'`<>]+',before);after_images=re.findall(r'data:image/[^\s\"\'`<>]+',after)
    assert sorted(before_images)==sorted(after_images),'Image preservation failed'
    assert re.findall(r'<style>.*?</style>',before,re.S)==re.findall(r'<style>.*?</style>',after,re.S),'CSS preservation failed'
    p.write_text(after)
    if args.export_workbook:extend_workbook(wb,after,covered);wb.save(args.export_workbook)
    print('Imported workbook; preserved all embedded images and CSS.')
    if args.export_workbook:print('Workbook:',args.export_workbook,'extra fields:',wb['기타 화면 문구'].max_row-4)
if __name__=='__main__':main()
