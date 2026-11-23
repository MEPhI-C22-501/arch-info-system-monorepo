Feature: Reading by the consumers

  Each consumer reads with the service account of its own client, the client ids and roles are those of the
  realm of Infra (document 160, section 4): Planning System `planning-service` (reference-hr-reader), Reports
  `reports-client` (reference-reader), Task Tracker `tracker-directory` (reference-reader), QA System `qa-executor`
  (reference-profile-reader). A consumer reads what its table row names and gets a refusal with the missing roles
  for anything else. A renamed or deleted record keeps its id, so a consumer cache is never broken by it.

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the SQL query from file "testdata/employee_in_effect.sql" is executed

  Scenario Outline: <client> reads <path>
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "<client>"
    When the HTTP request is sent to "<path>"
    Then an HTTP response is received with status 200

    Examples:
      | client            | path               |
      | planning-service  | /v1/employees/     |
      | planning-service  | /v1/org_units/     |
      | planning-service  | /v1/positions/     |
      | planning-service  | /v1/assignments/   |
      | planning-service  | /v1/absences/      |
      | planning-service  | /v1/project_roles/ |
      | planning-service  | /v1/grades/        |
      | planning-service  | /v1/profiles       |
      | reports-client    | /v1/employees/     |
      | reports-client    | /v1/org_units/     |
      | reports-client    | /v1/positions/     |
      | reports-client    | /v1/project_roles/ |
      | reports-client    | /v1/grades/        |
      | reports-client    | /v1/profiles       |
      | tracker-directory | /v1/employees/     |
      | tracker-directory | /v1/org_units/     |
      | tracker-directory | /v1/profiles       |
      | qa-executor       | /v1/profiles       |

  Scenario Outline: <client> is refused <path> and told which roles grant it
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "<client>"
    When the HTTP request is sent to "<path>"
    Then an HTTP response is received with status 403
    And the HTTP response contains a value at "/details/0/message"
      """
      "<reason>"
      """

    Examples:
      | client            | path            | reason                                                                                                                        |
      | qa-executor       | /v1/employees/  | read access to hr references needs one of the roles: reference-admin, reference-hr-admin, reference-hr-reader, reference-reader |
      | reports-client    | /v1/salaries/   | read access to restricted-hr references needs one of the roles: reference-hr-admin, reference-hr-reader                        |
      | tracker-directory | /v1/absences/   | read access to restricted-hr references needs one of the roles: reference-hr-admin, reference-hr-reader                        |

  Scenario: A renamed org unit keeps its id and reaches the profile of its employee
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=name
      """
    And the HTTP request contains a body
      """
      {"code": "dev-backend", "name": "Platform team", "kind": "TEAM", "parent_id": 1}
      """
    When the HTTP request is sent to "/v1/org_units/2"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "tracker-directory"
    When the HTTP request is sent to "/v1/org_units/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/name"
      """
      "Platform team"
      """
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "qa-executor"
    When the HTTP request is sent to "/v1/profiles"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/items/0/employeeId"
      """
      1
      """
    And the HTTP response contains a value at "/items/0/orgUnitId"
      """
      2
      """
    And the HTTP response contains a value at "/items/0/orgUnitName"
      """
      "Platform team"
      """

  Scenario: A deleted employee stays readable with its id and leaves the active profiles
    Given a DELETE HTTP request
    And the HTTP request is authorized as "hr-admin"
    When the HTTP request is sent to "/v1/employees/1"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "tracker-directory"
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employees"
      """
      []
      """
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "tracker-directory"
    And the HTTP request contains URL parameters
      """
      allowDeleted=true
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employees/0/id"
      """
      1
      """
    And the HTTP response contains a value at "/employees/0/is_deleted"
      """
      true
      """
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "qa-executor"
    When the HTTP request is sent to "/v1/profiles"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/items"
      """
      []
      """
    Given a GET HTTP request
    And the HTTP request is authorized as the service client "qa-executor"
    And the HTTP request contains URL parameters
      """
      includeInactive=true
      """
    When the HTTP request is sent to "/v1/profiles"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/items/0/isDeleted"
      """
      true
      """
    And the HTTP response contains a value at "/items/0/isActive"
      """
      false
      """
