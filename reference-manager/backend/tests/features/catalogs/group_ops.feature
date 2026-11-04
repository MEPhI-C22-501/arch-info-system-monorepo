Feature: Group operations over the employees of an org unit

  A revision of the salaries and a transfer to another unit from one date, each applied as a whole or not at all,
  with a check that returns the plan and changes nothing (FR-RM-63, FR-RM-64).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the SQL query from file "testdata/employee_in_effect.sql" is executed
    And the SQL query from file "testdata/group_ops.sql" is executed

  Scenario: A check of a salary revision of a unit with its subunits returns the plan and saves nothing
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 1, "include_subunits": true, "start_date": "2027-01-01", "percent": 10, "validate_only": true}
      """
    When the HTTP request is sent to "/v1/salaries/revise"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "validate_only": true,
        "items": [
          {"employee_id": 1, "closed_salary_id": 1, "previous_amount": 150000, "amount": 165000, "currency_id": 1, "start_date": "2027-01-01"},
          {"employee_id": 2, "closed_salary_id": 2, "previous_amount": 98765.43, "amount": 108641.97, "currency_id": 1, "start_date": "2027-01-01"}
        ],
        "skipped": [
          {"employee_id": 3, "reason": "the employee has no salary in effect on start_date"}
        ]
      }
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    And the HTTP request contains URL parameters
      """
      filter=start_date = "2027-01-01"
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {"salaries": []}
      """

  Scenario: A salary revision closes the salaries in effect and opens the new ones
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "start_date": "2027-01-01", "amount": 170000, "currency_id": 1}
      """
    When the HTTP request is sent to "/v1/salaries/revise"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/items/*/employee_id"
      """
      [1, 3]
      """
    And the HTTP response contains a value at "/items/*/salary_id"
      """
      [3, 4]
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    When the HTTP request is sent to "/v1/salaries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/end_date"
      """
      "2026-12-31"
      """
    And the HTTP response contains a value at "/revision"
      """
      2
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    And the HTTP request contains URL parameters
      """
      filter=start_date = "2027-01-01"
      order_by=employee_id
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/salaries/*/amount"
      """
      [170000, 170000]
      """

  Scenario: A salary revision is rejected as a whole when a salary starts on the date
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 1, "include_subunits": true, "start_date": "2025-03-01", "percent": 5}
      """
    When the HTTP request is sent to "/v1/salaries/revise"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "employees 2: the salary in effect starts on start_date, change it directly: failed precondition"}
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    When the HTTP request is sent to "/v1/salaries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revision"
      """
      1
      """

  Scenario: A salary revision checks its request
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "start_date": "2027-01-01", "percent": 5, "amount": 100000}
      """
    When the HTTP request is sent to "/v1/salaries/revise"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "validation failed", "details": [{"field": "amount", "message": "exactly one of percent and amount is allowed"}]}
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 99, "start_date": "2027-01-01", "percent": 5}
      """
    When the HTTP request is sent to "/v1/salaries/revise"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "validation failed", "details": [{"field": "org_unit_id", "message": "org unit 99 does not exist or is deleted"}]}
      """

  Scenario Outline: Group operations need the HR administrator
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains a body
      """
      <body>
      """
    When the HTTP request is sent to "<path>"
    Then an HTTP response is received with status 403

    Examples:
      | user      | path                    | body                                                                              |
      | reader    | /v1/salaries/revise     | {"org_unit_id": 2, "start_date": "2027-01-01", "percent": 5}                      |
      | hr-reader | /v1/salaries/revise     | {"org_unit_id": 2, "start_date": "2027-01-01", "percent": 5}                      |
      | admin     | /v1/salaries/revise     | {"org_unit_id": 2, "start_date": "2027-01-01", "percent": 5}                      |
      | admin     | /v1/assignments/transfer | {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01"}          |
      | hr-reader | /v1/assignments/transfer | {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01"}          |

  Scenario: A transfer moves the employees of a unit and keeps their positions
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01", "validate_only": true}
      """
    When the HTTP request is sent to "/v1/assignments/transfer"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "validate_only": true,
        "items": [
          {"employee_id": 1, "closed_assignment_id": 1, "org_unit_id": 2, "target_org_unit_id": 1, "position_id": 1, "start_date": "2027-01-01"},
          {"employee_id": 3, "closed_assignment_id": 3, "org_unit_id": 2, "target_org_unit_id": 1, "position_id": 1, "start_date": "2027-01-01"}
        ],
        "skipped": []
      }
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "target_org_unit_id": 1, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/assignments/transfer"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/validate_only"
      """
      false
      """
    And the HTTP response contains a value at "/items/*/employee_id"
      """
      [1, 3]
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=org_unit_id = 1 AND start_date = "2027-01-01"
      order_by=employee_id
      """
    When the HTTP request is sent to "/v1/assignments/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/assignments/*/employee_id"
      """
      [1, 3]
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/end_date"
      """
      "2026-12-31"
      """

  Scenario: A transfer to a missing unit is rejected and changes nothing
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"org_unit_id": 2, "target_org_unit_id": 99, "start_date": "2027-01-01"}
      """
    When the HTTP request is sent to "/v1/assignments/transfer"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "validation failed", "details": [{"field": "target_org_unit_id", "message": "org unit 99 does not exist or is deleted"}]}
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/assignments/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revision"
      """
      1
      """
