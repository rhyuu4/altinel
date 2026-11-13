#!/usr/bin/env python3
"""Export the current Altinel HTML/map copy as a macro-free editorial workbook."""
from pathlib import Path
import argparse,html,json,re,subprocess,tempfile
import openpyxl
from openpyxl.styles import Font,PatternFill,Alignment,Protection
from sync_text import Document,data_from,import_core,extra_rows

ROOT=Path(__file__).resolve().parents[1]

def export(output):
 source=(ROOT/'index.html').read_text();bundle=data_from(source);data=bundle['data'];doc=Document(source)
 maps=(ROOT/'assets/maps.js').read_text();fragment=maps[maps.index('const campus='):maps.index('function el(')]
 with tempfile.TemporaryDirectory() as directory:
  p=Path(directory)/'extract.cjs';p.write_text(fragment+'\nconsole.log(JSON.stringify({campus,world}));');regions=json.loads(subprocess.check_output(['node',str(p)]))
 map_copy=json.loads(re.search(r'const ATLAS_COPY=(.*?);\n',maps)[1])
 w=openpyxl.Workbook();w.remove(w.active)
 def sheet(name,title,info,headers,rows,editable,widths):
  sh=w.create_sheet(name);sh.append([title]);sh.append([info]);sh.append([]);sh.append(headers)
  for row in rows:sh.append(row)
  sh.freeze_panes='B5';sh.auto_filter.ref=f'A4:{openpyxl.utils.get_column_letter(len(headers))}{sh.max_row}';sh.sheet_view.showGridLines=False
  sh['A1'].font=Font(size=17,bold=True,color='24354B');sh['A2'].font=Font(size=10,color='66758A')
  for c in sh[4]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='24354B');c.alignment=Alignment(wrap_text=True,vertical='center')
  sh.row_dimensions[4].height=32
  for row in sh.iter_rows(min_row=5):
   for c in row:
    edit=c.column in editable;c.fill=PatternFill('solid',fgColor='FFF2CC' if edit else 'DCEAF7');c.alignment=Alignment(wrap_text=True,vertical='top');c.protection=Protection(locked=not edit)
    if isinstance(c.value,str):c.data_type='s'
   sh.row_dimensions[row[0].row].height=60
  for i,width in enumerate(widths,1):sh.column_dimensions[openpyxl.utils.get_column_letter(i)].width=width
  return sh
 info='노란색'+' 칸만 수정하세요. 파란색 ID·적용 위치는 유지해 주세요. 매크로 실행은 필요 없습니다.'
 cast_fields=['id','shortName','name','group','faction','nation','role','personality','tagline','description']
 sheet('등장인물 27명','등장인물 · 현재 사이트 27명',info,['ID(고정)','카드 이름','정식 이름','분류','계열','국가','역할','성격','한 줄 소개','상세 소개'],[[p.get(k,'') for k in cast_fields] for p in data['cast']],range(2,11),[12,18,26,18,16,25,32,28,50,85])
 boss_fields=['id','title','name','faction','nation','role','personality','tagline','description']
 sheet('보스 4명','보스 · 기본 비공개 / 공개 후 상세',info,['ID(고정)','비공개 호칭','정식 이름','계열','국가·지역','역할','성격','한 줄 소개','상세 소개'],[[p.get(k,'') for k in boss_fields] for p in data['bosses']],range(2,10),[12,18,26,16,26,35,28,55,90])
 fields=['circle','divine','martial','rank','implant','secretImplant','specialty'];people=data['cast']+data['bosses']
 sheet('전투 능력 31명','전투 능력 · 일반 인물 27명 + 보스 4명',info+' 빈칸은 미기재입니다.',['ID(고정)','인물명(확인용)','서클','신성력','무도','계급','괴수 이식','비공개 이식','전투 특기'],[[p['id'],p['name']]+[bundle['combat'][p['id']].get(k,'') for k in fields] for p in people],range(3,10),[12,26,18,20,24,22,42,48,90])
 def content(n):
  raw=source[n['inner']:n['end']];raw=re.sub(r'<br\s*/?>','\n',raw,flags=re.I);return html.unescape(re.sub(r'<[^>]+>','',raw))
 def ident(x):return doc.find(ident=x)
 def subtitle(x):
  n=ident(x);return next(t for t in doc.nodes if t['parent'] is n['parent'] and t['tag']=='p' and t['start']>n['end'])
 values={
 'heroEyebrow':content(doc.find(cls='hero-eyebrow')),
 'heroDesc':content(doc.find(cls='hero-sub'))}
 parts=re.split(r'<br\s*/?>',source[ident('hero-title')['inner']:ident('hero-title')['end']])
 assert len(parts)==3
 for key,part in zip(['heroTitleLine1','heroTitleLine2','heroTitleAccent'],parts):values[key]=html.unescape(re.sub(r'<[^>]+>','',part))
 for prefix,key in [('academy','academy-title'),('roster','roster-title'),('boss','targets-title'),('world','setting-title')]:values[prefix+'Title']=content(ident(key));values[prefix+'Subtitle']=content(subtitle(key))
 intro=doc.find(cls='academy-intro-copy')
 for key,tag in [('academyIntroTitle','strong'),('academyIntroText','p')]:values[key]=content(next(n for n in doc.nodes if n['parent'] is intro and n['tag']==tag))
 closing=doc.find(cls='closing-content')
 for key,tag in [('closingTitle','h2'),('closingSubtitle','p')]:values[key]=content(next(n for n in doc.nodes if n['parent'] is closing and n['tag']==tag and (tag!='p' or not n['attrs'].get('class'))))
 values['closingButton']=content(ident('site-chat-link'))
 locations={'heroEyebrow':'메인 / 작은 설명','heroTitleLine1':'메인 / 제목 1행','heroTitleLine2':'메인 / 제목 2행','heroTitleAccent':'메인 / 강조 제목','heroDesc':'메인 / 본문','academyTitle':'학교 생활 / 제목','academySubtitle':'학교 생활 / 설명','academyIntroTitle':'학교 생활 / 소개 제목','academyIntroText':'학교 생활 / 소개 본문','rosterTitle':'인물 / 제목','rosterSubtitle':'인물 / 설명','bossTitle':'전설 / 제목','bossSubtitle':'전설 / 설명','worldTitle':'지도 / 제목','worldSubtitle':'지도 / 설명','closingTitle':'하단 / 제목','closingSubtitle':'하단 / 설명','closingButton':'하단 / 버튼'}
 sheet('홈페이지 문구','홈페이지 주요 문구',info+' 셀 안 줄바꿈은 Alt+Enter입니다.',['문구 ID(고정)','적용 위치','현재 문구(수정)','비고'],[[k,location,values[k],'줄바꿈 유지 가능'] for k,location in locations.items()],[3],[25,32,100,30])
 schedule=[];tables=[n for n in doc.nodes if n['tag']=='tbody']
 for i,table in enumerate(tables,1):
  for row in [n for n in doc.nodes if n['tag']=='tr' and n['parent'] is table]:
   cells=[n for n in doc.nodes if n['tag']=='td' and n['parent'] is row];note=next((n for n in doc.nodes if n['parent'] is cells[1] and n['tag']=='span'),None)
   raw=source[cells[1]['inner']:note['start'] if note else cells[1]['end']]
   style={'danger-schedule':'주의','highlight-schedule':'강조'}.get(row['attrs'].get('class'),'일반')
   schedule.append([f'{i}학기',content(cells[0]),html.unescape(raw).strip(),content(note) if note else '',style])
 sheet('학사일정','학사일정 · 현재 11건',info,['학기','일정','행사','보조 설명','표시 스타일(일반/강조/주의)'],schedule,range(1,6),[15,23,35,60,30])
 # Legacy country data is retained only for compatibility, hidden from the editorial view.
 rows=[]
 for c in data['continents']:
  for n in c['nations']:rows.append([c['faction'],c['orientation'],c['summary'],n['name'],n['city'],n['text']])
 old=sheet('대륙과 국가','이전 국가 카드 자료 · 현재 화면 미사용','현재 지도 설명은 지도 지역 시트에서 수정하세요.',['계열','위치','소개','국가','도시','국가 설명'],rows,[],[16,26,60,26,22,80]);old.sheet_state='hidden'
 _,covered=import_core(source,w)
 skip={n['path'] for n in doc.nodes if n['attrs'].get('id')=='atlas-place-name' or any(c in n['attrs'].get('class','').split() for c in ('atlas-detail-kicker','atlas-map-note'))}
 extra=[r for r in extra_rows(source,covered) if not any(r[0].startswith('text:'+path+':') for path in skip) and not (r[0].startswith('attr:') and '/svg[' in r[0])]
 sheet('기타 화면 문구','메뉴 · 버튼 · 안내 · 상세창 · 검색 · 접근성',info,['문구 ID(고정)','적용 위치','현재 문구(수정)','비고'],extra,[3],[65,35,95,42])
 rows=[]
 for mode,items in regions.items():
  for item in items:rows.append([mode+'.'+item['id'],'교내 지도' if mode=='campus' else '세계지도',item['name'],item['category'],item['desc'],item.get('englishName','')])
 region_sheet=sheet('지도 지역','교내·세계지도 이름과 설명',info+' F열 영어는 교내·세계지도에 표시됩니다.',['ID(고정)','지도(고정)','이름','분류','설명','영어 이름'],rows,[3,4,5,6],[25,18,30,38,100,34])
 region_sheet.delete_rows(1,3);region_sheet.freeze_panes='C2';region_sheet.auto_filter.ref=f'A1:F{region_sheet.max_row}'
 descriptions={'campusTitle':'교내 지도 접근성 설명','worldTitle':'세계지도 접근성 설명','academyLink':'세계지도 / 교내 전환 글씨','academyLinkAria':'세계지도 / 교내 전환 접근성','campusKicker':'교내 설명 패널 상단','worldKicker':'세계 설명 패널 상단','detailsSuffix':'지역 선택 접근성 접미사','campusLegend':'교내 범례','worldLegend':'세계 범례','campusNote':'교내 하단 안내','worldNote':'세계 하단 안내','campusAria':'교내 지도 이름','worldAria':'세계지도 이름'}
 sheet('지도 공통 문구','지도 공통 안내 · 범례 · 접근성',info,['ID(고정)','적용 위치','현재 문구(수정)','비고'],[[k,descriptions.get(k,k),v,'지도 이름은 지도 지역에서 수정'] for k,v in map_copy.items()],[3],[28,35,100,40])
 usage=w.create_sheet('사용 방법',0);usage.sheet_view.showGridLines=False
 usage.append(['아카데미 알티넬 · 현재 사이트 텍스트 편집용']);usage.append(['기준일','2026-11-06 (한국 시간)']);usage.append(['기준 커밋',subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT).decode().strip()])
 usage.append(['시트','편집 내용','편집 칸'])
 for sh in w:
  if sh.title=='사용 방법' or sh.sheet_state=='hidden':continue
  usage.append([sh.title,'지역 이름·설명·영어 이름' if sh.title=='지도 지역' else sh['A1'].value,'노란색 셀'])
 for msg in ['노란색 셀만 수정하고 파란색 ID·적용 위치·행 순서를 유지해 주세요.','인물·보스의 숨김 정보와 전투 능력도 포함되어 있습니다. 일반 소개에 잘못 옮기지 않도록 주의하세요.','이름·설명은 지도 지역, 영어는 같은 시트 F열, 지도 안내는 지도 공통 문구에서 수정합니다.','빈칸은 미기재입니다. 의도하지 않은 항목을 지우지 마세요.','수정본을 채팅에 올리면 사이트에 반영할 수 있습니다. 엑셀 저장만으로 자동 배포되지는 않습니다.','이미지·지도 지형·위치·글씨 크기·클릭 범위는 이 파일에서 수정하지 않습니다.','현재 화면에 없는 예전 대륙·국가 카드는 숨긴 호환 시트에 보관했습니다. 지도 설명은 지도 지역 시트를 사용하세요.','매크로 없는 XLSX 파일이며 매크로 실행이 필요하지 않습니다.']:
  usage.append([msg])
 for col,width in [('A',65),('B',70),('C',25)]:usage.column_dimensions[col].width=width
 for row in usage:
  for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
  usage.row_dimensions[row[0].row].height=32
 usage['A1'].font=Font(size=18,bold=True,color='24354B');usage.freeze_panes='A5';w.active=0
 w.save(output)
 print('Saved:',output)
 print('Visible sheets:',[s.title for s in w if s.sheet_state=='visible'])
 return w
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args();export(args.output)
