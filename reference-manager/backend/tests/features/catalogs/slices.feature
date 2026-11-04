Feature: Records at a moment and the export of a selection

  List with readTime returns the records as they were at the moment, rebuilt from their revisions (FR-RM-61).
  Export takes the filter, the ordering and the moment of a list, deleted records stay out (FR-RM-62).

  Scenario: A slice shows a record with the name it had at the moment and hides a record created later
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-10T00:00:00Z
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "positions": [
          {
            "id": 1,
            "code": "qa",
            "name": "Tester",
            "is_deleted": false,
            "revision": 1,
            "last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "created_at": "2026-09-01T09:00:00Z",
            "updated_at": "2026-09-01T09:00:00Z",
            "deleted_at": "0001-01-01T00:00:00Z"
          }
        ]
      }
      """

  Scenario: A later slice shows the rename and the record created in between
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-25T00:00:00Z
      order_by=code
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/positions/*/name"
      """
      ["Analyst", "QA engineer"]
      """
    And the HTTP response contains a value at "/positions/*/revision"
      """
      [1, 2]
      """

  Scenario: A record deleted before the moment is hidden unless deleted records are allowed
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-10-05T00:00:00Z
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/positions/*/code"
      """
      ["analyst"]
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-10-05T00:00:00Z
      allowDeleted=true
      filter=code = "qa"
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/positions/0/is_deleted"
      """
      true
      """
    And the HTTP response contains a value at "/positions/0/deleted_at"
      """
      "2026-10-01T09:00:00Z"
      """

  Scenario: The filter of a slice applies to the values of the moment
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-10T00:00:00Z
      filter=name = "Tester"
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/positions/*/id"
      """
      [1]
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      allowDeleted=true
      filter=name = "Tester"
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {"positions": []}
      """

  Scenario: Dates of a dated record are rebuilt as calendar dates
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-10T00:00:00Z
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/salaries/0/start_date"
      """
      "2026-01-12"
      """
    And the HTTP response contains a value at "/salaries/0/amount"
      """
      150000
      """
    And the HTTP response contains a value at "/salaries/0/revision"
      """
      1
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-10-05T00:00:00Z
      filter=end_date = "2026-06-30"
      """
    When the HTTP request is sent to "/v1/salaries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/salaries/*/id"
      """
      [1]
      """

  Scenario: The currencies have a slice as well
    Given the SQL query from file "testdata/slices.sql" is executed
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-10T00:00:00Z
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/currencies/*/name"
      """
      ["Rouble"]
      """
    And the HTTP response contains a value at "/currencies/0/id"
      """
      1
      """

  Scenario: A moment that is not an RFC 3339 timestamp is rejected
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=yesterday
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 400

  Scenario: The export takes the filter and the ordering of the selection
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "dev", "name": "Developer"}
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "ops", "name": "Operations engineer"}
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "qa", "name": "QA engineer"}
      """
    When the HTTP request is sent to "/v1/positions/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=code != "qa"
      order_by=code desc
      """
    When the HTTP request is sent to "/v1/positions/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains an Excel sheet "Positions" with rows
      """
      | Code | Name                |
      | ops  | Operations engineer |
      | dev  | Developer           |
      """

  Scenario: The export of a slice holds the records as they were at the moment
    Given the SQL query from file "testdata/slices.sql" is executed
    And a POST HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      readTime=2026-09-25T00:00:00Z
      order_by=code
      """
    When the HTTP request is sent to "/v1/positions/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains an Excel sheet "Positions" with rows
      """
      | Code    | Name        | Revision |
      | analyst | Analyst     | 1        |
      | qa      | QA engineer | 2        |
      """

  Scenario: An export with a broken filter is rejected
    Given a POST HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=code =
      """
    When the HTTP request is sent to "/v1/positions/export"
    Then an HTTP response is received with status 400
