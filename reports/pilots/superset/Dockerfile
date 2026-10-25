FROM apache/superset:6.1.0
USER root
RUN uv pip install --no-cache 'Authlib==1.6.6' 'psycopg2-binary==2.9.11' 'PyJWT[crypto]==2.10.1'
COPY superset/cube_driver /tmp/reports-cube-driver
RUN uv pip install --no-cache --no-deps /tmp/reports-cube-driver && rm -rf /tmp/reports-cube-driver
COPY superset/superset_config.py superset/setup_bi.py superset/session_policy.py superset/check_session.py cube/dataset.sql /app/pythonpath/
USER superset
