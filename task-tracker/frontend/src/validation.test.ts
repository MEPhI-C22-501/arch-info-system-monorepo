import { describe, it, expect } from 'vitest';
import { validateItem } from './validation';
describe('task validation',()=>{
  it('rejects whitespace titles, reversed dates and negative hours',()=>{
    const errors=validateItem({title:' ',startDate:'2026-11-03',dueDate:'2026-11-02',plannedHours:'-1'});
    expect(Object.keys(errors)).toEqual(['title','dueDate','plannedHours']);
  });
  it('accepts zero estimate and two decimal places',()=>{
    expect(validateItem({title:'Задача',plannedHours:'0.25'})).toEqual({});
    expect(validateItem({title:'Задача',plannedHours:'0'})).toEqual({});
  });
  it('requires parents for subtasks and disallows direct epic estimates',()=>{
    expect(validateItem({title:'x',type:'SUBTASK'})).toHaveProperty('parentId');
    expect(validateItem({title:'x',type:'EPIC',parentId:'p',plannedHours:'4'})).toHaveProperty('plannedHours');
  });
});
