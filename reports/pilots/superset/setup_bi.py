"""Create a reproducible R-01 dashboard and mandatory Gamma row filter."""
import json
import os
import time
from pathlib import Path
from urllib.parse import quote
from superset.app import create_app

app = create_app()
with app.app_context():
    from superset import db, security_manager as sm
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice
    from superset.connectors.sqla.models import SqlaTable, SqlMetric, RowLevelSecurityFilter

    sm.add_role('ReportsNoAccess')
    admin = sm.find_user(username='pilot-bootstrap')
    if not admin:
        admin = sm.add_user('pilot-bootstrap', 'Pilot', 'Administrator', 'bootstrap@example.invalid',
                            sm.find_role('Admin'), os.environ['REPORTS_DEMO_ADMIN_PASSWORD'])
    database = db.session.query(Database).filter_by(database_name='Reports Cube').one_or_none()
    if database is None:
        database = Database(database_name='Reports Cube', expose_in_sqllab=False, allow_run_async=False,
                            allow_dml=False, allow_ctas=False, allow_cvas=False)
        db.session.add(database)
    database.set_sqlalchemy_uri('reports_cube+psycopg2://reports_bi:'+quote(os.environ['REPORTS_CUBE_SQL_PASSWORD'], safe='')+'@cube:15432/db')
    extra = database.get_extra()
    # Cube exposes PostgreSQL wire SQL, not PostgreSQL extensions. Avoid an
    # unnecessary pg_type/hstore probe each time SQLAlchemy opens a connection.
    extra.setdefault('engine_params', {})['use_native_hstore'] = False
    extra['engine_params']['isolation_level'] = 'AUTOCOMMIT'
    database.extra = json.dumps(extra)
    db.session.flush()
    dataset = db.session.query(SqlaTable).filter_by(table_name='reports_time_logs', database_id=database.id).one_or_none()
    if dataset is None:
        dataset = SqlaTable(table_name='reports_time_logs', database=database, owners=[admin])
        db.session.add(dataset)
    dataset.sql = Path(__file__).with_name('dataset.sql').read_text()
    # Superset starts only after the Cube SQL endpoint accepts a real query.
    for attempt in range(60):
        try:
            dataset.fetch_metadata()
            break
        except Exception:
            if attempt == 59: raise RuntimeError('Cube SQL endpoint did not become ready') from None
            time.sleep(2)
    if not any(m.metric_name == 'actual_hours' for m in dataset.metrics):
        dataset.metrics.append(SqlMetric(metric_name='actual_hours', verbose_name='Фактические часы', expression='SUM(hours)'))
    db.session.flush()
    gamma = sm.find_role('Gamma')
    sm.add_permission_role(gamma, sm.add_permission_view_menu('datasource_access', dataset.perm))
    rls = db.session.query(RowLevelSecurityFilter).filter_by(name='Reports member own hours').one_or_none()
    if rls is None:
        rls = RowLevelSecurityFilter(name='Reports member own hours'); db.session.add(rls)
    rls.filter_type = 'Regular'
    rls.roles, rls.tables = [gamma], [dataset]
    rls.clause = "user_id = '{{ current_username() }}'"
    chart = db.session.query(Slice).filter_by(slice_name='R-01 Трудозатраты').one_or_none()
    if chart is None:
        chart = Slice(slice_name='R-01 Трудозатраты', owners=[admin]); db.session.add(chart)
    chart.datasource_id, chart.datasource_type, chart.viz_type = dataset.id, 'table', 'table'
    chart.params = json.dumps({'viz_type': 'table', 'datasource': f'{dataset.id}__table', 'query_mode': 'aggregate',
                              'groupby': ['project_id', 'user_id'], 'metrics': ['actual_hours'], 'row_limit': 1000})
    db.session.flush()
    dashboard = db.session.query(Dashboard).filter_by(slug='reports-r01').one_or_none()
    if dashboard is None:
        dashboard = Dashboard(dashboard_title='R-01 Трудозатраты', slug='reports-r01', owners=[admin]); db.session.add(dashboard)
    dashboard.published = True
    dashboard.slices = [chart]
    dashboard.position_json = json.dumps({
        'DASHBOARD_VERSION_KEY': 'v2',
        'ROOT_ID': {'id': 'ROOT_ID', 'type': 'ROOT', 'children': ['GRID_ID']},
        'GRID_ID': {'id': 'GRID_ID', 'type': 'GRID', 'children': ['ROW-1'], 'parents': ['ROOT_ID']},
        'ROW-1': {'id': 'ROW-1', 'type': 'ROW', 'children': ['CHART-1'], 'parents': ['ROOT_ID', 'GRID_ID'], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}},
        'CHART-1': {'id': 'CHART-1', 'type': 'CHART', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID', 'ROW-1'],
                    'meta': {'chartId': chart.id, 'height': 60, 'width': 12, 'sliceName': chart.slice_name}},
    })

    # R-06 plan-fact for analysts. Their access is global, so they are not in Gamma and the
    # member RLS above does not apply; members get neither R-06 dataset, so the dashboard
    # is not listed for them. Plan side is the WorkItems rollup, fact side the TimeLogs one (ADR-018).
    sm.copy_role('Gamma', 'ReportsAnalyst', merge=True)
    analyst = sm.find_role('ReportsAnalyst')

    def virtual_dataset(name, sql_file, metrics, time_column=None):
        table = db.session.query(SqlaTable).filter_by(table_name=name, database_id=database.id).one_or_none()
        if table is None:
            table = SqlaTable(table_name=name, database=database, owners=[admin]); db.session.add(table)
        table.sql = Path(__file__).with_name(sql_file).read_text()
        table.fetch_metadata()
        table.main_dttm_col = time_column
        for metric_name, verbose_name, expression in metrics:
            if not any(m.metric_name == metric_name for m in table.metrics):
                table.metrics.append(SqlMetric(metric_name=metric_name, verbose_name=verbose_name, expression=expression))
        db.session.flush()
        sm.add_permission_role(analyst, sm.add_permission_view_menu('datasource_access', table.perm))
        return table

    def table_chart(name, table, params):
        # Read the id first: the permission commit expired the dataset, and loading it later
        # would autoflush a new chart that has no datasource yet.
        table_id = table.id
        found = db.session.query(Slice).filter_by(slice_name=name).one_or_none()
        if found is None:
            found = Slice(slice_name=name, owners=[admin], datasource_id=table_id, datasource_type='table', viz_type='table')
            db.session.add(found)
        found.datasource_id, found.datasource_type, found.viz_type = table_id, 'table', 'table'
        found.params = json.dumps(dict(params, viz_type='table', datasource=f'{table_id}__table', query_mode='aggregate', row_limit=1000))
        return found

    plan = virtual_dataset('reports_plan_by_project', 'plan_by_project.sql',
                           [('planned_hours', 'План, ч', 'SUM(planned_hours)'), ('remaining_hours', 'Остаток, ч', 'SUM(remaining_hours)'),
                            ('tasks', 'Задач', 'SUM(tasks)')])
    fact = virtual_dataset('reports_fact_by_project', 'fact_by_project.sql',
                           [('fact_hours', 'Факт за период, ч', 'SUM(hours)')], time_column='logged_date')
    plan_chart = table_chart('R-06 План и остаток по проектам', plan,
                             {'groupby': ['project_id'], 'metrics': ['planned_hours', 'remaining_hours', 'tasks']})
    fact_chart = table_chart('R-06 Факт за период по проектам', fact,
                             {'groupby': ['project_id'], 'metrics': ['fact_hours'], 'granularity_sqla': 'logged_date', 'time_range': 'No filter',
                              'adhoc_filters': [{'clause': 'WHERE', 'expressionType': 'SIMPLE', 'subject': 'logged_date',
                                                 'operator': 'TEMPORAL_RANGE', 'comparator': 'No filter'}]})
    db.session.flush()
    plan_fact = db.session.query(Dashboard).filter_by(slug='reports-r06').one_or_none()
    if plan_fact is None:
        plan_fact = Dashboard(dashboard_title='R-06 План-факт', slug='reports-r06', owners=[admin]); db.session.add(plan_fact)
    plan_fact.published = True
    plan_fact.slices = [plan_chart, fact_chart]
    note = ('План и остаток — по текущему составу задач проекта, факт — часы за период из фильтра «Период». '
            'Точный R-06 с планом задач на конец периода и областью руководителя проекта — в Reports UI.')
    plan_fact.position_json = json.dumps({
        'DASHBOARD_VERSION_KEY': 'v2',
        'ROOT_ID': {'id': 'ROOT_ID', 'type': 'ROOT', 'children': ['GRID_ID']},
        'GRID_ID': {'id': 'GRID_ID', 'type': 'GRID', 'children': ['ROW-1', 'ROW-2'], 'parents': ['ROOT_ID']},
        'ROW-1': {'id': 'ROW-1', 'type': 'ROW', 'children': ['MARKDOWN-1'], 'parents': ['ROOT_ID', 'GRID_ID'], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}},
        'MARKDOWN-1': {'id': 'MARKDOWN-1', 'type': 'MARKDOWN', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID', 'ROW-1'],
                       'meta': {'code': note, 'height': 15, 'width': 12}},
        'ROW-2': {'id': 'ROW-2', 'type': 'ROW', 'children': ['CHART-1', 'CHART-2'], 'parents': ['ROOT_ID', 'GRID_ID'], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}},
        'CHART-1': {'id': 'CHART-1', 'type': 'CHART', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID', 'ROW-2'],
                    'meta': {'chartId': plan_chart.id, 'height': 50, 'width': 6, 'sliceName': plan_chart.slice_name}},
        'CHART-2': {'id': 'CHART-2', 'type': 'CHART', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID', 'ROW-2'],
                    'meta': {'chartId': fact_chart.id, 'height': 50, 'width': 6, 'sliceName': fact_chart.slice_name}},
    })
    plan_fact.json_metadata = json.dumps({
        'native_filter_configuration': [{
            'id': 'NATIVE_FILTER-period', 'name': 'Период', 'filterType': 'filter_time', 'type': 'NATIVE_FILTER',
            'targets': [{}], 'controlValues': {}, 'cascadeParentIds': [], 'description': '',
            'defaultDataMask': {'filterState': {'value': 'No filter'}, 'extraFormData': {}},
            'scope': {'rootPath': ['ROOT_ID'], 'excluded': [plan_chart.id]},
        }],
        'refresh_frequency': 0, 'color_scheme': '', 'label_colors': {}, 'shared_label_colors': [],
    })
    db.session.commit()
    print('R-01 and R-06 dashboards, member RLS and analyst role configured')
