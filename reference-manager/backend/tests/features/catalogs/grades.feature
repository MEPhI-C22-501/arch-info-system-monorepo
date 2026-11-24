Feature: Grade of an assignment and stable codes

  The grade is an optional dated value of the assignment, the employee shows the grade of the assignment in effect
  today (FR-RM-69). The codes of project roles, grades, org units and positions are set on creation and never change,
  so consumers may keep them as references (BR-RM-18, ADR-027).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the SQL query from file "testdata/employee_in_effect.sql" is executed

  Scenario: The employee shows the grade of the assignment in effect and a transfer keeps it
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "senior", "name": "Senior", "rank": 3}
      """
    When the HTTP request is sent to "/v1/grades/"
    Then an HTTP response is received with status 201
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=grade_id
      """
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 2, "position_id": 1, "grade_id": 1, "start_date": "2024-01-15"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/grade_id"
      """
      1
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/employees/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/grade_id"
      """
      1
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/assignments/transfer"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=employee_id = 1 AND start_date = "2027-01-01"
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments/*/grade_id"
      """
      [1]
      """
    And the HTTP response contains a value at "/assignments/*/org_unit_id"
      """
      [1]
      """

  Scenario: An assignment may have no grade, a grade it names must exist
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=NOT grade_id:*
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments/*/id"
      """
      [1]
      """
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=grade_id
      """
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 2, "position_id": 1, "grade_id": 99, "start_date": "2024-01-15"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "validation failed", "details": [{"field": "grade_id", "message": "grades 99 does not exist"}]}
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "junior", "name": "Junior", "rank": 1}
      """
    When the HTTP request is sent to "/v1/grades/"
    Then an HTTP response is received with status 201
    Given a DELETE HTTP request
    And the HTTP request is authorized as "admin"
    When the HTTP request is sent to "/v1/grades/1"
    Then an HTTP response is received with status 200
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=grade_id
      """
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 2, "position_id": 1, "grade_id": 1, "start_date": "2024-01-15"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "validation failed", "details": [{"field": "grade_id", "message": "grades 1 is deleted"}]}
      """

  Scenario: A deleted grade does not block closing the assignment, a transfer that would copy it is rejected
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "senior", "name": "Senior", "rank": 3}
      """
    When the HTTP request is sent to "/v1/grades/"
    Then an HTTP response is received with status 201
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=grade_id
      """
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 2, "position_id": 1, "grade_id": 1, "start_date": "2024-01-15"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    Given a DELETE HTTP request
    And the HTTP request is authorized as "admin"
    When the HTTP request is sent to "/v1/grades/1"
    Then an HTTP response is received with status 200
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/assignments/transfer"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/details/0/field"
      """
      "grade_id"
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2026-12-31"}
      """
    When the HTTP request is sent to "/v1/employees/1/dismiss"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/end_date"
      """
      "2026-12-31"
      """
    And the HTTP response contains a value at "/grade_id"
      """
      1
      """

  Scenario: A slice of the assignments shows the grade from the moment it was set
    Given the SQL query from file "testdata/grade_slice.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-11-01T00:00:00Z
      filter=grade_id:*
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments"
      """
      []
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-11-20T00:00:00Z
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments/*/grade_id"
      """
      [1]
      """
    And the HTTP response contains a value at "/assignments/*/start_date"
      """
      ["2024-01-15"]
      """

  Scenario Outline: The code of <path> is set on creation and cannot be changed
    Given a PATCH HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains URL parameters
      """
      updateMask=code
      """
    And the HTTP request contains a body
      """
      <body>
      """
    When the HTTP request is sent to "<path>"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/message"
      """
      "invalid updateMask: field \"code\" cannot be updated, updatable fields: <updatable>"
      """

    Examples:
      | path            | user     | body                                                            | updatable             |
      | /v1/org_units/1 | hr-admin | {"code": "changed", "name": "Development", "kind": "DEPARTMENT"} | name, kind, parent_id |
      | /v1/positions/1 | hr-admin | {"code": "changed", "name": "Software developer"}               | name                  |

  Scenario Outline: The code of a <collection> record is set on creation and cannot be changed
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      <body>
      """
    When the HTTP request is sent to "/v1/<collection>/"
    Then an HTTP response is received with status 201
    Given a PATCH HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains URL parameters
      """
      updateMask=code
      """
    And the HTTP request contains a body
      """
      <changed>
      """
    When the HTTP request is sent to "/v1/<collection>/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/message"
      """
      "invalid updateMask: field \"code\" cannot be updated, updatable fields: <updatable>"
      """
    Given a PATCH HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains URL parameters
      """
      updateMask=name
      """
    And the HTTP request contains a body
      """
      <renamed>
      """
    When the HTTP request is sent to "/v1/<collection>/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/code"
      """
      "<code>"
      """

    Examples:
      | collection    | body                                            | changed                                          | renamed                                           | code      | updatable         |
      | project_roles | {"code": "developer", "name": "Developer"}      | {"code": "changed", "name": "Developer"}         | {"code": "developer", "name": "Renamed"}          | developer | name, description |
      | grades        | {"code": "senior", "name": "Senior", "rank": 3} | {"code": "changed", "name": "Senior", "rank": 3} | {"code": "senior", "name": "Renamed", "rank": 3}  | senior    | name, rank        |
