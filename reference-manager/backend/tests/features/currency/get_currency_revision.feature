Feature: Currency revision retrieval

  Background:
    Given the SQL query from file "testdata/currency_revisions.sql" is executed
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """

  Scenario: Revision is returned with its change
    When the HTTP request is sent to "/v1/currencies/1/revisions/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a body from file "testdata/usd_revision_renamed"

  Scenario: Revision created through the API is returned
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c |
      """
    And the HTTP request contains a body
      """
      {
        "code": "EUR",
        "number": "978",
        "name": "Euro",
        "decimals": 2,
        "is_deleted": false
      }
      """
    And the HTTP request is sent to "/v1/currencies/"
    And an HTTP response is received with status 201
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the HTTP request is sent to "/v1/currencies/3/revisions/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "id": 6,
        "currency_id": 3,
        "revision_number": 1,
        "change": [
          {"op": "add", "path": "/code", "value": "EUR"},
          {"op": "add", "path": "/decimals", "value": 2},
          {"op": "add", "path": "/is_deleted", "value": false},
          {"op": "add", "path": "/name", "value": "Euro"},
          {"op": "add", "path": "/number", "value": "978"}
        ],
        "changed_by": "9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c",
        "changed_at": "{{any}}"
      }
      """

  Scenario Outline: Revision of a deleted currency is returned when <case>
    Given the HTTP request contains URL parameters
      """
      allowDeleted=<allow_deleted>
      """
    When the HTTP request is sent to "/v1/currencies/2/revisions/2"
    Then an HTTP response is received with status <status>
    And the HTTP response contains a body from file "<body>"

    Examples:
      | case                     | allow_deleted | status | body                          |
      | deleted ones are allowed | true          | 200    | testdata/rur_revision_deleted |
      | deleted ones are hidden  | false         | 404    | testdata/not_found            |

  Scenario: Revision of a deleted currency is hidden by default
    When the HTTP request is sent to "/v1/currencies/2/revisions/1"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario: Missing revision is not found
    When the HTTP request is sent to "/v1/currencies/1/revisions/4"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/revision_not_found"

  Scenario: Revision of a missing currency is not found
    When the HTTP request is sent to "/v1/currencies/3/revisions/1"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario Outline: Revision is not returned without a valid user (<case>)
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions/1"
    Then an HTTP response is received with status 401
    And the HTTP response contains a body
      """
      {
        "message": "unauthenticated"
      }
      """

    Examples:
      | case             | user_id  |
      | header is absent |          |
      | invalid UUID     | not-uuid |

  Scenario Outline: Revision is not returned for invalid parameters (<case>)
    Given the HTTP request contains URL parameters
      """
      allowDeleted=<allow_deleted>
      """
    When the HTTP request is sent to "/v1/currencies/<currency_id>/revisions/<revision_number>"
    Then an HTTP response is received with status 400
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a body
      """
      {
        "message": "invalid request parameters"
      }
      """

    Examples:
      | case                        | currency_id | revision_number | allow_deleted |
      | non-numeric currency ID     | abc         | 1               | false         |
      | non-numeric revision number | 1           | abc             | false         |
      | non-boolean allowDeleted    | 1           | 1               | maybe         |
