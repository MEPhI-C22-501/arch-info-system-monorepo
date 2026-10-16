Feature: Currency deletion

  Background:
    Given the SQL query from file "testdata/currencies.sql" is executed
    And a DELETE HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c |
      """

  Scenario: Currency is soft-deleted with a new revision
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
        "is_deleted": true,
        "revision": 2,
        "last_changer": "9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c",
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "{{any}}",
        "deleted_at": "{{any}}"
      }
      """
    When the SQL query is executed
      """
      SELECT id, code, is_deleted FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | id | code | is_deleted |
      | 1  | USD  | t          |
      """
    When the SQL query is executed
      """
      SELECT revision_number, changed_by, op.value ->> 'op' AS op, op.value ->> 'path' AS path, op.value -> 'value' AS value
      FROM currency_revisions, jsonb_array_elements(change) AS op
      WHERE currency_id = 1 AND revision_number = 2;
      """
    Then the query result is received
      """
      | revision_number | changed_by                           | op      | path        | value |
      | 2               | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c | replace | /is_deleted | true  |
      """
    When the SQL query is executed
      """
      SELECT deleted_at = updated_at AS deleted_is_updated FROM v_expanded_currency WHERE id = 1;
      """
    Then the query result is received
      """
      | deleted_is_updated |
      | t                  |
      """

  Scenario: Soft-deleted currency is hidden afterwards
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c |
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario Outline: Currency is not soft-deleted when it is <case>
    When the HTTP request is sent to "/v1/currencies/<currency_id>"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"
    When the SQL query is executed
      """
      SELECT count(*) AS revisions FROM currency_revisions;
      """
    Then the query result is received
      """
      | revisions |
      | 7         |
      """

    Examples:
      | case            | currency_id |
      | already deleted | 5           |
      | missing         | 100         |

  Scenario Outline: Currency is permanently deleted with its revisions when it is <case>
    Given the HTTP request contains URL parameters
      """
      force=true
      """
    When the HTTP request is sent to "/v1/currencies/<currency_id>"
    Then an HTTP response is received with status 204
    When the SQL query is executed
      """
      SELECT
        (SELECT count(*) FROM currencies WHERE id = <currency_id>) AS currencies,
        (SELECT count(*) FROM currency_revisions WHERE currency_id = <currency_id>) AS revisions,
        (SELECT count(*) FROM currencies) AS remaining;
      """
    Then the query result is received
      """
      | currencies | revisions | remaining |
      | 0          | 0         | 5         |
      """

    Examples:
      | case    | currency_id |
      | active  | 1           |
      | deleted | 5           |

  Scenario: Missing currency is not permanently deleted
    Given the HTTP request contains URL parameters
      """
      force=true
      """
    When the HTTP request is sent to "/v1/currencies/100"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario Outline: Currency is not deleted without a valid user (<case>)
    Given a DELETE HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    And the HTTP request contains URL parameters
      """
      force=<force>
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 401
    And the HTTP response contains a body
      """
      {
        "message": "unauthenticated"
      }
      """
    When the SQL query is executed
      """
      SELECT is_deleted FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | is_deleted |
      | f          |
      """

    Examples:
      | case                           | user_id  | force |
      | header is absent               |          | false |
      | invalid UUID                   | not-uuid | false |
      | header is absent, forced       |          | true  |

  Scenario Outline: Currency is not deleted for invalid parameters (<case>)
    Given the HTTP request contains URL parameters
      """
      force=<force>
      """
    When the HTTP request is sent to "/v1/currencies/<currency_id>"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "invalid request parameters"
      }
      """

    Examples:
      | case                    | currency_id | force |
      | non-numeric currency ID | abc         | false |
      | non-boolean force       | 1           | maybe |
