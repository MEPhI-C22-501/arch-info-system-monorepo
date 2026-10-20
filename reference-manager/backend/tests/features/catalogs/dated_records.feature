Feature: Dated records of employees

  Assignments, salaries and absences carry a period, periods of one employee do not overlap in assignments and
  salaries, a new value is a new record (FR-RM-51, FR-RM-52, BR-RM-16).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the SQL query from file "testdata/employee_in_effect.sql" is executed

  Scenario: A new assignment that overlaps the one in effect is rejected until the old one is closed
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 1, "position_id": 1, "start_date": "2026-10-01"}
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "invalid start_date, end_date: period overlaps another record of the employee"}
      """
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=end_date
      """
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 2, "position_id": 1, "start_date": "2024-01-15", "end_date": "2026-09-30"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/end_date"
      """
      "2026-09-30"
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 1, "org_unit_id": 1, "position_id": 1, "start_date": "2026-10-01"}
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/start_date"
      """
      "2026-10-01"
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=employee_id = 1 AND start_date <= "2026-06-15" AND (end_date >= "2026-06-15" OR NOT end_date:*)
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments/*/org_unit_id"
      """
      [2]
      """

  Scenario: The employee of an assignment cannot be changed and references must be active
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=employee_id
      """
    And the HTTP request contains a body
      """
      {"employee_id": 2, "org_unit_id": 2, "position_id": 1, "start_date": "2024-01-15"}
      """
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/message"
      """
      "invalid updateMask: field \"employee_id\" cannot be updated, updatable fields: org_unit_id, position_id, start_date, end_date"
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 7, "org_unit_id": 9, "position_id": 1, "start_date": "2027-01-01", "end_date": "2026-01-01"}
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "end_date", "message": "must not be earlier than start_date"},
          {"field": "employee_id", "message": "employees 7 does not exist"},
          {"field": "org_unit_id", "message": "org_units 9 does not exist"}
        ]
      }
      """

  Scenario: Salaries need a positive amount and an active currency
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 1, "amount": 0, "currency_id": 5, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "amount", "message": "must be at least 0.01"}
        ]
      }
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 1, "amount": 180000.5, "currency_id": 1, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/message"
      """
      "invalid start_date, end_date: period overlaps another record of the employee"
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    When the HTTP request is sent to "/v1/salaries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/amount"
      """
      150000
      """

  Scenario: Absences need an ordered period and an existing employee
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 1, "kind": "VACATION", "start_date": "2026-07-06", "end_date": "2026-07-19"}
      """
    When the HTTP request is sent to "/v1/absences/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/kind"
      """
      "VACATION"
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"employee_id": 3, "kind": "SICK_LEAVE", "start_date": "2026-07-19", "end_date": "2026-07-06"}
      """
    When the HTTP request is sent to "/v1/absences/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "end_date", "message": "must not be earlier than start_date"},
          {"field": "employee_id", "message": "employees 3 does not exist"}
        ]
      }
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    And the HTTP request contains URL parameters
      """
      filter=employee_id = 1 AND start_date <= "2026-12-31" AND end_date >= "2026-07-01"
      """
    When the HTTP request is sent to "/v1/absences/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/absences/*/kind"
      """
      ["VACATION"]
      """
