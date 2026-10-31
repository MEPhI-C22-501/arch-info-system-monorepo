import { FormEvent, useState } from 'react';
import type { Severity } from '../api/client';
import { Template, TemplateInput, createTemplate, listAllTemplates, updateTemplate } from '../api/templates';
import { StepDraft } from '../caseForm';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { StepsEditor, newStep } from '../components/StepsEditor';
import { useToast } from '../components/Toast';
import { useLoad } from '../useLoad';
import { optionsOf, useClassifiers } from '../useReferenceData';

type Draft = {
  id?: string;
  name: string;
  description: string;
  isActive: boolean;
  bodyDescription: string;
  preconditions: string;
  priority: string;
  severity: string;
  type: string;
  steps: StepDraft[];
};

const EMPTY: Draft = { name: '', description: '', isActive: true, bodyDescription: '', preconditions: '', priority: '', severity: '', type: '', steps: [] };

function draftOf(template: Template): Draft {
  const { body } = template;
  return {
    id: template.id,
    name: template.name,
    description: template.description ?? '',
    isActive: template.isActive,
    bodyDescription: body.description ?? '',
    preconditions: body.preconditions ?? '',
    priority: body.priority ?? '',
    severity: body.severity ?? '',
    type: body.type ?? '',
    steps: (body.steps ?? []).map((step) => newStep(step.action, step.expectedResult)),
  };
}

function inputOf(draft: Draft): TemplateInput {
  return {
    name: draft.name,
    description: draft.description || undefined,
    isActive: draft.isActive,
    body: {
      description: draft.bodyDescription || undefined,
      preconditions: draft.preconditions || undefined,
      priority: draft.priority || undefined,
      severity: (draft.severity || undefined) as Severity | undefined,
      type: draft.type || undefined,
      steps: draft.steps.map(({ action, expectedResult }) => ({ action, expectedResult })),
    },
  };
}

export function AdminTemplates() {
  const toast = useToast();
  const templates = useLoad(() => listAllTemplates(), ['templates']);
  const classifiers = useClassifiers();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<unknown>(null);

  const toggle = async (template: Template) => {
    setError(null);
    try {
      await updateTemplate(template.id, { name: template.name, description: template.description, body: template.body, isActive: !template.isActive });
      toast(template.isActive ? `Шаблон «${template.name}» отключён` : `Шаблон «${template.name}» включён`);
      templates.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    setError(null);
    try {
      if (draft.id) await updateTemplate(draft.id, inputOf(draft));
      else await createTemplate(inputOf(draft));
      toast(`Шаблон «${draft.name}» сохранён`);
      setDraft(null);
      templates.reload();
    } catch (failure) {
      setError(failure);
    }
  };

  const columns: Column<Template>[] = [
    { header: 'Шаблон', render: (row) => <>{row.name}{row.description && <div className="muted">{row.description}</div>}</> },
    { header: 'Шагов', render: (row) => row.body.steps?.length ?? 0 },
    { header: 'Активен', render: (row) => (row.isActive ? 'да' : 'нет') },
    {
      header: 'Действия',
      render: (row) => (
        <div className="bar" style={{ marginBottom: 0 }}>
          <button type="button" onClick={() => setDraft(draftOf(row))}>Изменить</button>
          <button type="button" onClick={() => toggle(row)}>{row.isActive ? 'Отключить' : 'Включить'}</button>
        </div>
      ),
    },
  ];
  const select = (name: 'priority' | 'severity' | 'type', kind: 'PRIORITY' | 'SEVERITY' | 'CASE_TYPE', label: string) => draft && (
    <Field label={label}>
      <select className="wide" value={draft[name]} onChange={(event) => setDraft({ ...draft, [name]: event.target.value })}>
        <option value="">—</option>
        {optionsOf(classifiers.data, kind, draft[name]).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </Field>
  );

  return (
    <>
      <div className="bar"><button type="button" className="primary" onClick={() => setDraft({ ...EMPTY })}>Создать шаблон</button></div>
      <ErrorMessage error={error} />
      <div className="panel">
        <DataTable columns={columns} rows={templates.data} rowKey={(row) => row.id} loading={templates.loading} error={templates.error} onRetry={templates.reload} emptyText="Шаблонов нет" />
      </div>
      {draft && (
        <form className="panel" onSubmit={submit}>
          <h3>{draft.id ? `Шаблон «${draft.name}»` : 'Новый шаблон'}</h3>
          <Field label="Название"><input type="text" required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></Field>
          <Field label="Описание шаблона"><input type="text" value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></Field>
          <div className="fields">
            {select('priority', 'PRIORITY', 'Приоритет')}
            {select('severity', 'SEVERITY', 'Серьёзность')}
            {select('type', 'CASE_TYPE', 'Тип')}
          </div>
          <Field label="Описание кейса"><textarea rows={2} value={draft.bodyDescription} onChange={(event) => setDraft({ ...draft, bodyDescription: event.target.value })} /></Field>
          <Field label="Предусловия"><textarea rows={2} value={draft.preconditions} onChange={(event) => setDraft({ ...draft, preconditions: event.target.value })} /></Field>
          <h3>Шаги</h3>
          <StepsEditor steps={draft.steps} onChange={(steps) => setDraft({ ...draft, steps })} />
          <div className="bar" style={{ marginTop: 12, marginBottom: 0 }}>
            <button type="submit" className="primary">Сохранить</button>
            <button type="button" onClick={() => setDraft(null)}>Отмена</button>
          </div>
        </form>
      )}
    </>
  );
}
