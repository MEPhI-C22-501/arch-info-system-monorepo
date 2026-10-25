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
    db.session.commit()
    print('R-01 dashboard and member RLS configured')
