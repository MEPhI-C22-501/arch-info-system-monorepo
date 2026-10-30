"""Atomic timeline changes: work tree, FS successors, demands and assignments."""
import copy
from datetime import date, timedelta
from .domain import fail, validate_draft


def reschedule(plan, identifier, start, finish):
    result=copy.deepcopy(plan)
    items={x['id']:x for x in result['items']}
    before={x['id']:x for x in plan['items']}
    if identifier not in items:fail(404,'Работа не найдена')
    if start>finish:fail(422,'Начало позже окончания')
    item=items[identifier]
    if item['type']=='MILESTONE' and start!=finish:fail(422,'Веха должна иметь одну дату')

    def shift(node, days):
        x=items[node]
        for key in ['start','finish']:x[key]=(date.fromisoformat(x[key])+timedelta(days=days)).isoformat()
        for child in result['items']:
            if child['parentItemId']==node:shift(child['id'],days)

    delta=(date.fromisoformat(start)-date.fromisoformat(item['start'])).days
    moving=(date.fromisoformat(finish)-date.fromisoformat(item['finish'])).days==delta
    if moving:shift(identifier,delta)
    else:
        item.update(start=start,finish=finish)
        children=[x for x in items.values() if x['parentItemId']==identifier]
        if any(x['start']<start or x['finish']>finish for x in children):
            fail(422,'Группа должна вмещать дочерние работы. Перенесите группу целиком или измените работы внутри неё.')

    # Expand ancestors and push successors until both tree and FS constraints settle.
    # Ancestor/descendant dependency loops are rejected rather than drifting forever.
    for _ in range((len(items)+len(result['dependencies'])+1)*2):
        changed=False
        for x in items.values():
            if not x['parentItemId']:continue
            parent=items[x['parentItemId']]
            left=min(parent['start'],x['start']);right=max(parent['finish'],x['finish'])
            if (left,right)!=(parent['start'],parent['finish']):
                if parent['type']=='MILESTONE':fail(422,'Веха не может содержать работы')
                parent.update(start=left,finish=right);changed=True
        for dep in result['dependencies']:
            predecessor=items[dep['predecessorId']];successor=items[dep['successorId']]
            earliest=date.fromisoformat(predecessor['finish'])
            for _ in range(dep['lagWorkingDays']+1):
                earliest+=timedelta(days=1)
                while earliest.weekday()>4:earliest+=timedelta(days=1)
            if successor['start']<earliest.isoformat():
                shift(successor['id'],(earliest-date.fromisoformat(successor['start'])).days);changed=True
        if not changed:break
    else:fail(422,'Зависимости и структура не позволяют согласовать сроки')

    changed_ids={k for k,v in items.items() if (v['start'],v['finish'])!=(before[k]['start'],before[k]['finish'])}
    for demand in result['demands']:
        key=demand['planItemId']
        if key not in changed_ids:continue
        old=before[key];new=items[key]
        days=(date.fromisoformat(new['start'])-date.fromisoformat(old['start'])).days
        previous_start=demand['periodStart'];previous_end=demand['periodEnd']
        def bounded(value):return min(max(value,new['start']),new['finish'])
        demand['periodStart']=bounded((date.fromisoformat(previous_start)+timedelta(days=days)).isoformat())
        demand['periodEnd']=new['finish'] if previous_end==old['finish'] else bounded((date.fromisoformat(previous_end)+timedelta(days=days)).isoformat())
        for allocation in result['allocations']:
            if allocation['demandId']!=demand['id']:continue
            # Cancelled history stays cancelled, while its date remains contract-valid.
            moved=(date.fromisoformat(allocation['date'])+timedelta(days=days)).isoformat()
            allocation['date']=min(max(moved,demand['periodStart']),demand['periodEnd'])
            if allocation['status']!='CANCELLED':allocation['status']='PROPOSED'
    # A timeline move never silently extends the explicitly chosen plan horizon.
    validate_draft(result)
    return result,sorted(changed_ids)
