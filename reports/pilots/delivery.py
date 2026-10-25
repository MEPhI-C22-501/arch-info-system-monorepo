"""Safe file encoders and timezone-aware five-field cron scheduling."""
import csv
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo
from report_engine import Problem


def cell(value):
    if isinstance(value,dict) and set(value)>={'id','label'}: value=value['label']
    if isinstance(value,(dict,list)): return json.dumps(value,ensure_ascii=False,sort_keys=True)
    return value if value is not None else ''


def safe_text(value):
    value=str(value)
    value=''.join(c for c in value if ord(c)>=32 or c in '\t\n\r')
    if value.lstrip(' \t\r\n\ufeff').startswith(('=','+','-','@')) or value.startswith(('\t','\r')): value="'"+value
    return value


def matrix(result,query,author):
    keys=[c['key'] for c in result['columns']]
    return [['report',result['reportId']],['author',author],['generatedAt',result['generatedAt']],
            ['parameters',json.dumps(query,ensure_ascii=False,sort_keys=True)],
            ['freshness',json.dumps(result['freshness'],ensure_ascii=False,sort_keys=True)],
            ['notes',json.dumps(result['notes'],ensure_ascii=False)],[],keys,
            *[[cell(row.get(k)) for k in keys] for row in result['rows']],
            ['TOTALS',json.dumps(result['totals'],ensure_ascii=False,sort_keys=True)]]


def encode(result,query,author,fmt):
    rows=matrix(result,query,author)
    if fmt=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out)
        for row in rows: writer.writerow([safe_text(v) if isinstance(v,str) else v for v in row])
        return b'\xef\xbb\xbf'+out.getvalue().encode(), 'text/csv; charset=utf-8'
    if fmt!='xlsx': raise Problem(422,'INVALID_PARAMETER')
    # Inline strings never create formulas, external links, shared strings or macros.
    sheet=[]
    for index,row in enumerate(rows,1):
        cells=[]
        for value in row:
            if type(value) in (int,float): cells.append('<c><v>'+str(value)+'</v></c>')
            else:
                text=''.join(c for c in str(value) if (0x20<=ord(c)<=0xD7FF or 0xE000<=ord(c)<=0xFFFD or 0x10000<=ord(c)<=0x10FFFF or c in '\t\n\r'))
                cells.append('<c t="inlineStr"><is><t xml:space="preserve">'+escape(text)+'</t></is></c>')
        sheet.append('<row r="'+str(index)+'">'+''.join(cells)+'</row>')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(sheet)+'</sheetData></worksheet>')
    return out.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def printable(result,query,author):
    rows=matrix(result,query,author)
    body=''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)
    return ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>'+escape(result['reportId'])+'</title><table>'+body+'</table></html>').encode()


def cron_fields(expression):
    if not isinstance(expression,str) or len(expression)>128 or len(expression.split())!=5: raise Problem(422,'INVALID_SCHEDULE')
    result=[]
    for text,(low,high) in zip(expression.split(),[(0,59),(0,23),(1,31),(1,12),(0,6)]):
        values=set()
        try:
            for part in text.split(','):
                if not re.fullmatch(r'(?:\*|\d+(?:-\d+)?)(?:/\d+)?',part): raise ValueError()
                base,_,step=part.partition('/'); step=int(step) if step else 1
                if not 1<=step<=high-low+1: raise ValueError()
                start,end=(low,high) if base=='*' else tuple(map(int,base.split('-'))) if '-' in base else (int(base),int(base))
                if not low<=start<=end<=high: raise ValueError()
                values.update(range(start,end+1,step))
        except (ValueError,TypeError): raise Problem(422,'INVALID_SCHEDULE') from None
        result.append(values)
    return result


def next_run(expression,after,zone='Europe/Moscow'):
    minute,hour,dom,month,dow=cron_fields(expression);tz=ZoneInfo(zone)
    local=after.astimezone(tz); candidates=[]; wildcard=expression.split()
    for offset in range(366*5):
        observed=local.date()+timedelta(days=offset)
        if observed.month not in month: continue
        md=observed.day in dom; wd=(observed.weekday()+1)%7 in dow
        if not ((md or wd) if wildcard[2]!='*' and wildcard[4]!='*' else md and wd): continue
        for h in sorted(hour):
            for m in sorted(minute):
                for fold in (0,1):
                    value=datetime(observed.year,observed.month,observed.day,h,m,tzinfo=tz,fold=fold).astimezone(timezone.utc)
                    back=value.astimezone(tz)
                    if value>after and (back.date(),back.hour,back.minute)==(observed,h,m): candidates.append(value)
        if candidates: return min(candidates).isoformat()
    raise Problem(422,'INVALID_SCHEDULE')
