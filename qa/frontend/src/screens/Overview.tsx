import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { PlanSummary, getPlanSummary, listAllPlans } from '../api/plans';
import { Run, listRuns } from '../api/runs';
import { SuitePurpose, listSuites } from '../api/suites';
import { Column, DataTable } from '../components/DataTable';
import { ErrorMessage } from '../components/ErrorMessage';
import { Field } from '../components/Field';
import { StatusBadge } from '../components/StatusBadge';
import { SEVERITIES, formatDateTime } from '../labels';
import { useLoad } from '../useLoad';
import { SummaryCounters } from './PlanCard';

type OpenDefect = PlanSummary['openDefects'][number];

const DEFECT_COLUMNS: Column<OpenDefect>[] = [
  { header: 'Ключ', render: (row) => row.key },
  { header: 'Заголовок', render: (row) => row.title },
  { header: 'Серьёзность', render: (row) => <StatusBadge status={row.severity} /> },
  { header: 'Статус', render: (row) => <StatusBadge status={row.status} kind="defect" /> },
];

// Последний прогон набора: «Приёмка стенда» и «Smoke» ищутся по назначению, а не по имени.
async function lastRunOf(purpose: SuitePurpose): Promise<{ suiteName?: string; run?: Run }> {
  const suites = await listSuites({ purpose, pageSize: 1 });
  const suite = suites.items[0];
  if (!suite) return {};
  const runs = await listRuns({ suiteId: suite.id, pageSize: 1 });
  return { suiteName: suite.name, run: runs.items[0] };
}

function SuiteTile({ purpose, title, emptyText }: { purpose: SuitePurpose; title: string; emptyText: string }) {
  const last = useLoad(() => lastRunOf(purpose), [purpose]);
  const run = last.data?.run;
  return (
    <div className="panel">
      <h3>{title}</h3>
      <ErrorMessage error={last.error} onRetry={last.reload} />
      {last.loading && !last.data && <span className="skeleton" />}
      {last.data && !run && <p className="muted" style={{ marginBottom: 0 }}>{emptyText}</p>}
      {run && (
        <>
          <p><Link to={`/runs/${run.id}`}>{run.key}</Link> <StatusBadge status={run.status} /> · {run.environment} · {formatDateTime(run.finishedAt ?? run.startedAt ?? run.createdAt)}</p>
          <p style={{ marginBottom: 0 }}>
            Пройдено {run.summary.passed}, упало {run.summary.failed}, не проверено {run.summary.notRun + run.summary.unverified}
            {purpose === 'SMOKE' && run.smokeVerdict && <> · <StatusBadge status={run.smokeVerdict} /></>}
            {purpose === 'ACCEPTANCE' && (run.verdict ? <> · вердикт <StatusBadge status={run.verdict} /></> : <span className="muted"> · вердикт не ставился</span>)}
          </p>
        </>
      )}
    </div>
  );
}

function PlanOverview({ planId }: { planId: string }) {
  const navigate = useNavigate();
  const summary = useLoad(() => getPlanSummary(planId), [planId]);
  if (summary.error) return <ErrorMessage error={summary.error} onRetry={summary.reload} />;
  if (!summary.data) return <p className="muted" aria-busy="true">Загрузка…</p>;
  const { counters, openDefects } = summary.data;
  const hasResults = counters.notRun < counters.total;
  return (
    <>
      {!hasResults && <div className="panel"><div className="empty">По плану ещё нет прогонов</div></div>}
      <SummaryCounters counters={counters} />
      <div className="grid">
        {SEVERITIES.map((severity) => (
          <div key={severity} className="stat"><b className={severity}>{openDefects.filter((defect) => defect.severity === severity).length}</b>{severity}</div>
        ))}
      </div>
      <div className="panel">
        <h3>Открытые дефекты</h3>
        <DataTable
          columns={DEFECT_COLUMNS}
          rows={openDefects}
          rowKey={(row) => row.id}
          onOpen={(row) => navigate(`/defects/${row.id}`)}
          emptyText="Открытых дефектов нет"
        />
      </div>
    </>
  );
}

export function Overview() {
  const plans = useLoad(() => listAllPlans(), ['plans']);
  const [chosen, setChosen] = useState('');
  const planId = chosen || plans.data?.[0]?.id || '';

  return (
    <>
      <h2>Состояние тестирования</h2>
      <ErrorMessage error={plans.error} onRetry={plans.reload} />
      {plans.data && plans.data.length === 0 && <div className="panel"><div className="empty">Планов пока нет</div></div>}
      {plans.data && plans.data.length > 0 && (
        <>
          <div className="bar">
            <div style={{ minWidth: 320 }}>
              <Field label="План">
                <select className="wide" value={planId} onChange={(event) => setChosen(event.target.value)}>
                  {plans.data.map((plan) => <option key={plan.id} value={plan.id}>{plan.key} {plan.name}</option>)}
                </select>
              </Field>
            </div>
            <Link className="btn" to={`/plans/${planId}`}>К плану</Link>
          </div>
          <PlanOverview planId={planId} />
        </>
      )}
      <div className="fields">
        <SuiteTile purpose="ACCEPTANCE" title="Приёмка стенда" emptyText="Приёмка ещё не проводилась" />
        <SuiteTile purpose="SMOKE" title="Smoke" emptyText="«Smoke» ещё не запускался: автотестов пока нет" />
      </div>
    </>
  );
}
