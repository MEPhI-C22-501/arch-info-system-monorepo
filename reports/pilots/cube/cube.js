'use strict';

const { rewrite } = require('./access');

module.exports = {
  schemaPath: 'model',
  telemetry: false,
  jwt: {
    jwkUrl: process.env.REPORTS_OIDC_JWKS_URL,
    // Cube 1.6.75 otherwise suppresses unknown-kid refresh for 60 seconds.
    // Keep a bounded refresh rate while supporting local Keycloak rotation.
    jwkRefetchWindow: 5000,
    issuer: [process.env.REPORTS_OIDC_ISSUER],
    audience: 'reports',
    algorithms: ['RS256'],
  },
  queryRewrite: rewrite,
  // The shared SQL identity is restricted to the private BI network. End-user
  // RLS is applied by Superset; members have no SQL Lab / database permissions.
  canSwitchSqlUser: () => false,
  checkSqlAuth: async (_req, user) => {
    if (user !== 'reports_bi' || !process.env.REPORTS_CUBE_SQL_PASSWORD) throw new Error('SQL identity denied');
    return {
      password: process.env.REPORTS_CUBE_SQL_PASSWORD,
      securityContext: { resource_access: { reports: { roles: ['reports-bi-service'] } } },
    };
  },
};
