// runtime configuration of the panel: the API is served under the same origin by the routing in front of the service,
// Keycloak is the address the browser reaches it at; another stand mounts its own copy of this file at /admin/js/config.js
window.RM_CONFIG = {
  apiBase: '/v1',
  keycloak: {
    url: 'http://localhost:8180',
    realm: 'arch-info-system',
    clientId: 'reference-manager-ui',
    // the client whose roles are read from resource_access besides the realm roles
    rolesClient: 'reference-manager',
  },
};
