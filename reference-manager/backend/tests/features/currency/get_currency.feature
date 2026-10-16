Feature: Currency retrieval

  Scenario: Currency is returned with its revision metadata
    Given the SQL query is executed
      """
      INSERT INTO currencies (code, number, name, decimals) VALUES ('USD', '840', 'US Dollar', 2);
      INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at)
      VALUES (1, 1, '[{"op": "add", "path": "/code", "value": "USD"}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-05 07:54:00+00');
      """
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a body
      """
      {
        "code": "USD",
        "number": "840",
        "name": "US Dollar",
        "decimals": 2,
        "is_deleted": false,
        "revision": 1,
        "last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "created_at": "2026-10-05T07:54:00Z",
        "updated_at": "2026-10-05T07:54:00Z",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """

  Scenario Outline: Deleted currency is returned when <case>
    Given the SQL query is executed
      """
      INSERT INTO currencies (code, number, name, decimals, is_deleted) VALUES ('USD', '840', 'US Dollar', 2, TRUE);
      INSERT INTO currency_revisions (currency_id, revision_number, change, changed_by, changed_at) VALUES
        (1, 1, '[{"op": "add", "path": "/is_deleted", "value": false}]', '3fa85f64-5717-4562-b3fc-2c963f66afa6', '2026-10-05 07:54:00+00'),
        (1, 2, '[{"op": "replace", "path": "/is_deleted", "value": true}]', '9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c', '2026-10-06 07:54:00+00');
      """
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains URL parameters
      """
      allowDeleted=<allow_deleted>
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status <status>
    And the HTTP response contains a body from file "<body>"

    Examples:
      | case                     | allow_deleted | status | body                 |
      | deleted ones are allowed | true          | 200    | testdata/usd_deleted |
      | deleted ones are hidden  | false         | 404    | testdata/not_found   |

  Scenario: Deleted currency is hidden by default
    Given the SQL query is executed
      """
      INSERT INTO currencies (code, number, name, decimals, is_deleted) VALUES ('USD', '840', 'US Dollar', 2, TRUE);
      """
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario: Missing currency is not found
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario Outline: Currency is not returned without a valid user (<case>)
    Given the SQL query is executed
      """
      INSERT INTO currencies (code, number, name, decimals) VALUES ('USD', '840', 'US Dollar', 2);
      """
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    When the HTTP request is sent to "/v1/currencies/1"
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

  Scenario Outline: Currency is not returned for invalid parameters (<case>)
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains URL parameters
      """
      allowDeleted=<allow_deleted>
      """
    When the HTTP request is sent to "/v1/currencies/<currency_id>"
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
      | case                     | currency_id | allow_deleted |
      | non-numeric currency ID  | abc         | false         |
      | non-boolean allowDeleted | 1           | maybe         |
