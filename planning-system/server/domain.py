from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException

def fail(code, message): raise HTTPException(code, message)
def hours(v): return Decimal(str(v))

def validate_draft(d):
    if d['horizonStart'] > d['horizonEnd']: fail(422, 'Неверный горизонт')
    items = {i['id']:i for i in d['items']}
    if len(items)!=len(d['items']) or len({i['logicalItemId'] for i in d['items']})!=len(items): fail(422,'Дубли элементов')
    def cycle(edges):
        visited=set(); pending=set()
        def visit(n):
            if n in pending: fail(422,'Цикл в структуре или зависимостях')
            if n in visited:return
            pending.add(n)
            for child in edges.get(n,[]):visit(child)
            pending.remove(n);visited.add(n)
        for n in edges:visit(n)
    tree={}; fs={}
    for i in items.values():
        if not d['horizonStart'] <= i['start'] <= i['finish'] <= d['horizonEnd']:fail(422,'Элемент вне горизонта')
        if i['type']=='MILESTONE' and (i['start']!=i['finish'] or i['plannedHours']!=0):fail(422,'Веха имеет одну дату и ноль часов')
        if i['parentItemId']:
            if i['parentItemId'] not in items:fail(422,'Родитель из другой версии')
            parent=items[i['parentItemId']]
            if not parent['start']<=i['start']<=i['finish']<=parent['finish']:fail(422,'Ребёнок вне дат родителя')
            tree.setdefault(i['parentItemId'],[]).append(i['id'])
    cycle(tree)
    for dep in d['dependencies']:
        if dep['predecessorId'] not in items or dep['successorId'] not in items:fail(422,'Чужая зависимость')
        fs.setdefault(dep['predecessorId'],[]).append(dep['successorId'])
        end=date.fromisoformat(items[dep['predecessorId']]['finish'])
        for _ in range(dep['lagWorkingDays']+1):
            end+=timedelta(days=1)
            while end.weekday()>4:end+=timedelta(days=1)
        if date.fromisoformat(items[dep['successorId']]['start'])<end:fail(422,'Нарушена FS-зависимость')
    cycle(fs)
    demands={v['id']:v for v in d['demands']}
    if len(demands)!=len(d['demands']):fail(422,'Дубли потребностей')
    for v in demands.values():
        i=items.get(v['planItemId'])
        if not i or i['id'] in tree:fail(422,'Потребность задаётся листу этой версии')
        if not i['start']<=v['periodStart']<=v['periodEnd']<=i['finish']:fail(422,'Потребность вне дат работы')
    if len({a['id'] for a in d['allocations']})!=len(d['allocations']):fail(422,'Дубли назначений')
    for a in d['allocations']:
        demand=demands.get(a['demandId'])
        if not demand or not demand['periodStart']<=a['date']<=demand['periodEnd']:fail(422,'Назначение вне потребности')

def check_resources(d, availability, other_allocations=()):
    totals={}; assigned={}
    for a in [*other_allocations,*d['allocations']]:
        if a['status']=='CANCELLED':continue
        k=(a['employeeId'],a['date']);totals[k]=totals.get(k,Decimal(0))+hours(a['hours'])
    for a in d['allocations']:
        if a['status']=='CANCELLED':continue
        if a['status']!='CONFIRMED':fail(422,'Назначение не подтверждено')
        k=(a['employeeId'],a['date']);v=availability.get(k)
        if not v or v['status']!='CONFIRMED' or totals[k]>hours(v['availableHours']):fail(422,'Нет доступности или перегрузка')
        assigned[a['demandId']]=assigned.get(a['demandId'],Decimal(0))+hours(a['hours'])
    for demand in d['demands']:
        if assigned.get(demand['id'],Decimal(0))!=hours(demand['hours']):fail(422,'Дефицит или превышение потребности')

def forecast(tasks, etc, rate=None, baseline=None):
    missing=[]
    actual=sum((hours(t['actualHours']) for t in tasks if not t['isDeleted']),Decimal(0))
    if etc is None:missing.append('ETC');remaining=None
    else:remaining=hours(etc)
    if rate is None:missing.append('RATE')
    cost=(actual+remaining)*hours(rate) if remaining is not None and rate is not None else None
    return {'actualHours':float(actual),'remainingHours':float(remaining) if remaining is not None else None,
            'quality':'PARTIAL' if missing else 'COMPLETE','missingInputs':missing,
            'estimatedTotalCost':float(cost) if cost is not None else None,
            'budgetAdjustment':float(cost-hours(baseline)) if cost is not None and baseline is not None else None}
