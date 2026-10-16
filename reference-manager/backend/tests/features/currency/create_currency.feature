Feature: Currency creation

  Scenario: Currency is created with the first revision
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains a body from file "testdata/usd"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 201
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a body from file "testdata/usd_created"
    When the SQL query is executed
      """
      SELECT id, code, number, name, decimals, is_deleted FROM currencies;
      """
    Then the query result is received
      """
      | id | code | number | name      | decimals | is_deleted |
      | 1  | USD  | 840    | US Dollar | 2        | f          |
      """
    When the SQL query is executed
      """
      SELECT currency_id, revision_number, changed_by FROM currency_revisions;
      """
    Then the query result is received
      """
      | currency_id | revision_number | changed_by                           |
      | 1           | 1               | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the SQL query is executed
      """
      SELECT op.value ->> 'op' AS op, op.value ->> 'path' AS path, op.value -> 'value' AS value
      FROM currency_revisions, jsonb_array_elements(change) AS op
      ORDER BY path;
      """
    Then the query result is received
      """
      | op  | path        | value       |
      | add | /code       | "USD"       |
      | add | /decimals   | 2           |
      | add | /is_deleted | false       |
      | add | /name       | "US Dollar" |
      | add | /number     | "840"       |
      """
    When the SQL query is executed
      """
      SELECT created_at = updated_at AS created_is_updated, deleted_at FROM v_expanded_currency;
      """
    Then the query result is received
      """
      | created_is_updated | deleted_at |
      | t                  | NULL       |
      """

  Scenario Outline: Currency <code> keeps its numeric code and minor units
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains a body
      """
      {
        "code": "<code>",
        "number": "<number>",
        "name": "<name>",
        "decimals": <decimals>,
        "is_deleted": false
      }
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a body
      """
      {
        "code": "<code>",
        "number": "<number>",
        "name": "<name>",
        "decimals": <decimals>,
        "is_deleted": false,
        "revision": 1,
        "last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "created_at": "{{any}}",
        "updated_at": "{{any}}",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """
    When the SQL query is executed
      """
      SELECT code, number, name, decimals FROM currencies;
      """
    Then the query result is received
      """
      | code   | number   | name   | decimals   |
      | <code> | <number> | <name> | <decimals> |
      """

    Examples:
      | code | number | name              | decimals |
      | JPY  | 392    | Yen               | 0        |
      | ALL  | 008    | Lek               | 2        |
      | BHD  | 048    | Bahraini Dinar    | 3        |
      | CLF  | 990    | Unidad de Fomento | 4        |

  Scenario Outline: Currency is not created when <case>
    Given the SQL query is executed
      """
      INSERT INTO currencies (code, number, name, decimals) VALUES ('USD', '840', 'US Dollar', 2);
      """
    And a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains a body
      """
      {
        "code": "<code>",
        "number": "<number>",
        "name": "Duplicate",
        "decimals": 2,
        "is_deleted": false
      }
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 409
    And the HTTP response contains a body
      """
      {
        "message": "currency already exists"
      }
      """
    When the SQL query is executed
      """
      SELECT
        (SELECT count(*) FROM currencies) AS currencies,
        (SELECT count(*) FROM currency_revisions) AS revisions;
      """
    Then the query result is received
      """
      | currencies | revisions |
      | 1          | 0         |
      """

    Examples:
      | case                        | code | number |
      | the code is already taken   | USD  | 999    |
      | the number is already taken | XXX  | 840    |

  Scenario Outline: Currency is not created without a valid user (<case>)
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    And the HTTP request contains a body from file "testdata/usd"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 401
    And the HTTP response contains a body
      """
      {
        "message": "unauthenticated"
      }
      """
    When the SQL query is executed
      """
      SELECT count(*) AS currencies FROM currencies;
      """
    Then the query result is received
      """
      | currencies |
      | 0          |
      """

    Examples:
      | case             | user_id  |
      | header is absent |          |
      | invalid UUID     | not-uuid |

  Scenario: Currency is not created from a malformed body
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains a body
      """
      {"code": "USD",
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "failed to decode request"
      }
      """
    When the SQL query is executed
      """
      SELECT count(*) AS currencies FROM currencies;
      """
    Then the query result is received
      """
      | currencies |
      | 0          |
      """
