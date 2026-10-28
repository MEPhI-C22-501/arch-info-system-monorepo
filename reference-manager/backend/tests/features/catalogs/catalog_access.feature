Feature: Access to the catalogs by group

  Classifiers are changed by reference-admin, HR catalogs by reference-hr-admin, every role reads both groups.
  Salaries and absences are read by the HR roles only (documents/070.role-matrix.md).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed

  Scenario Outline: A classifier is changed by reference-admin only
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains a body
      """
      {"code": "analyst", "name": "Analyst"}
      """
    When the HTTP request is sent to "/v1/project_roles/"
    Then an HTTP response is received with status <status>

    Examples:
      | user      | status |
      | admin     | 201    |
      | hr-admin  | 403    |
      | reader    | 403    |
      | hr-reader | 403    |
      | outsider  | 403    |

  Scenario Outline: An HR catalog is changed by reference-hr-admin only
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains a body
      """
      {"code": "qa-engineer", "name": "QA engineer"}
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status <status>

    Examples:
      | user      | status |
      | hr-admin  | 201    |
      | admin     | 403    |
      | reader    | 403    |
      | hr-reader | 403    |
      | outsider  | 403    |

  Scenario Outline: HR catalogs are read by every role of the service
    Given a GET HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status <status>

    Examples:
      | user      | status |
      | reader    | 200    |
      | hr-reader | 200    |
      | admin     | 200    |
      | hr-admin  | 200    |
      | outsider  | 403    |

  Scenario Outline: Salaries and absences are read by the HR roles only
    Given the SQL query from file "testdata/employee_in_effect.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status <status>
    Given a GET HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/absences/"
    Then an HTTP response is received with status <status>
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/salaries/export"
    Then an HTTP response is received with status <status>

    Examples:
      | user      | status |
      | hr-reader | 200    |
      | hr-admin  | 200    |
      | reader    | 403    |
      | admin     | 403    |

  Scenario: A request without a token is rejected
    Given a GET HTTP request
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 401
