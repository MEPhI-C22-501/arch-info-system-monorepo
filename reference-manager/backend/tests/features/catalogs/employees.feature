Feature: Employees

  An employee is hired as EMPLOYED with a Keycloak account, the unit and the position come from the assignment
  in effect today, the dismissal closes the assignment and the salary in effect with the dismissal date
  and blocks the account (FR-RM-49, FR-RM-53, FR-RM-54).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the Keycloak account "m.petrova" is removed
    And the Keycloak account "i.ivanov" is removed

  Scenario: An employee is hired with an account, the account result is the second revision
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a body
      """
      {
        "id": 2,
        "personnel_number": "1024",
        "family_name": "Petrova",
        "given_name": "Maria",
        "email": "m.petrova@example.org",
        "username": "m.petrova",
        "hire_date": "2026-11-02",
        "employment_state": "EMPLOYED",
        "account_state": "ENABLED",
        "account_user_id": "{{any}}",
        "is_deleted": false,
        "revision": 2,
        "last_changer": "d81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d",
        "created_at": "{{any}}",
        "updated_at": "{{any}}",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """

  Scenario: A taken login or email and a bad personnel number are rejected
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "A1", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "i.ivanov", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "personnel_number", "message": "must match ^[0-9]{1,10}$"}
        ]
      }
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "i.ivanov", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 409

  Scenario: The unit and the position of an employee come from the assignment in effect
    Given the SQL query from file "testdata/employee_in_effect.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/employees/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/org_unit_id"
      """
      2
      """
    And the HTTP response contains a value at "/position_id"
      """
      1
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=employment_state = "EMPLOYED" AND org_unit_id = 2
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employees/*/personnel_number"
      """
      ["1001"]
      """

  Scenario: A record other records refer to is not purged
    Given the SQL query from file "testdata/employee_in_effect.sql" is executed
    And a DELETE HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      force=true
      """
    When the HTTP request is sent to "/v1/employees/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "delete employee: employee 1 is referenced by records of other catalogs: failed precondition"}
      """

  Scenario: The dismissal closes the assignment and the salary in effect
    Given the SQL query from file "testdata/employee_in_effect.sql" is executed
    And a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2026-10-31"}
      """
    When the HTTP request is sent to "/v1/employees/1/dismiss"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employment_state"
      """
      "DISMISSED"
      """
    And the HTTP response contains a value at "/dismissal_date"
      """
      "2026-10-31"
      """
    And the HTTP response contains a value at "/account_state"
      """
      "DISABLED"
      """
    And the HTTP response contains a value at "/revision"
      """
      3
      """
    When the SQL query is executed
      """
      SELECT id, end_date FROM assignments ORDER BY id;
      """
    Then the query result is received
      """
      | id | end_date   |
      | 1  | 2026-10-31 |
      """
    When the SQL query is executed
      """
      SELECT id, end_date FROM salaries ORDER BY id;
      """
    Then the query result is received
      """
      | id | end_date   |
      | 1  | 2026-10-31 |
      """
    When the SQL query is executed
      """
      SELECT assignment_id, revision_number FROM assignment_revisions ORDER BY revision_number;
      """
    Then the query result is received
      """
      | assignment_id | revision_number |
      | 1             | 1               |
      | 1             | 2               |
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2026-11-30"}
      """
    When the HTTP request is sent to "/v1/employees/1/dismiss"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "employee 1 is already dismissed on 2026-10-31: failed precondition"}
      """

  Scenario: A dismissal before the hire date and a dismissal by the wrong role are rejected
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2020-01-01"}
      """
    When the HTTP request is sent to "/v1/employees/1/dismiss"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "dismissal_date", "message": "must not be earlier than hire_date"}
        ]
      }
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2026-10-31"}
      """
    When the HTTP request is sent to "/v1/employees/1/dismiss"
    Then an HTTP response is received with status 403

  Scenario: Employees are exported with their dates
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-reader"
    When the HTTP request is sent to "/v1/employees/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains an Excel sheet "Employees" with rows
      """
      | Personnel number | Family name | Username | Hire date  | Employment state |
      | 1001             | Ivanov      | i.ivanov | 2024-01-15 | EMPLOYED         |
      """
