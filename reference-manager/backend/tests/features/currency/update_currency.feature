Feature: Currency update

  Background:
    Given the SQL query from file "testdata/currencies.sql" is executed
    And a PATCH HTTP request
    And the HTTP request is authorized as "second-admin"

  Scenario: Fields from the update mask are updated with a new revision
    Given the HTTP request contains URL parameters
      """
      updateMask=name
      """
    And the HTTP request contains a body
      """
      {
        "code": "XXX",
        "number": "999",
        "name": "United States Dollar",
        "decimals": 4,
        "is_deleted": false
      }
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
        "name": "United States Dollar",
        "decimals": 2,
        "is_deleted": false,
        "revision": 2,
        "last_changer": "9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c",
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "{{any}}",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """
    When the SQL query is executed
      """
      SELECT id, code, number, name, decimals, is_deleted FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | id | code | number | name                 | decimals | is_deleted |
      | 1  | USD  | 840    | United States Dollar | 2        | f          |
      """
    When the SQL query is executed
      """
      SELECT revision_number, changed_by, op.value ->> 'op' AS op, op.value ->> 'path' AS path, op.value -> 'value' AS value
      FROM currency_revisions, jsonb_array_elements(change) AS op
      WHERE currency_id = 1 AND revision_number = 2;
      """
    Then the query result is received
      """
      | revision_number | changed_by                           | op      | path  | value                  |
      | 2               | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c | replace | /name | "United States Dollar" |
      """

  Scenario Outline: All updatable fields are updated when the mask is <case>
    Given the HTTP request contains URL parameters
      """
      updateMask=<mask>
      """
    And the HTTP request contains a body
      """
      {
        "code": "USX",
        "number": "841",
        "name": "United States Dollar",
        "decimals": 3,
        "is_deleted": true
      }
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "code": "USX",
        "number": "841",
        "name": "United States Dollar",
        "decimals": 3,
        "is_deleted": false,
        "revision": 2,
        "last_changer": "9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c",
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "{{any}}",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """
    When the SQL query is executed
      """
      SELECT op.value ->> 'path' AS path, op.value -> 'value' AS value
      FROM currency_revisions, jsonb_array_elements(change) AS op
      WHERE currency_id = 1 AND revision_number = 2
      ORDER BY path;
      """
    Then the query result is received
      """
      | path      | value                  |
      | /code     | "USX"                  |
      | /decimals | 3                      |
      | /name     | "United States Dollar" |
      | /number   | "841"                  |
      """

    Examples:
      | case     | mask                      |
      | absent   |                           |
      | wildcard | *                         |
      | explicit | code,number,name,decimals |

  Scenario: Currency without changes keeps its revision
    Given the HTTP request contains a body from file "testdata/usd"
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 200
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
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": "2026-10-01T10:00:00Z",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """
    When the SQL query is executed
      """
      SELECT count(*) AS revisions FROM currency_revisions WHERE currency_id = 1;
      """
    Then the query result is received
      """
      | revisions |
      | 1         |
      """

  Scenario Outline: Currency is not updated when the mask contains <case>
    Given the HTTP request contains URL parameters
      """
      updateMask=<mask>
      """
    And the HTTP request contains a body from file "testdata/usd_renamed"
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "invalid updateMask: field \"<field>\" cannot be updated, updatable fields: code, number, name, decimals"
      }
      """
    When the SQL query is executed
      """
      SELECT name FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | name      |
      | US Dollar |
      """

    Examples:
      | case               | mask            | field      |
      | a read-only field  | name,is_deleted | is_deleted |
      | an unknown field   | symbol          | symbol     |
      | an empty field     | name,           |            |

  Scenario Outline: Currency is not updated when the <field> is already taken
    Given the HTTP request contains URL parameters
      """
      updateMask=<field>
      """
    And the HTTP request contains a body
      """
      {
        "code": "EUR",
        "number": "978",
        "name": "US Dollar",
        "decimals": 2,
        "is_deleted": false
      }
      """
    When the HTTP request is sent to "/v1/currencies/1"
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
        (SELECT code || ' ' || number FROM currencies WHERE id = 1) AS usd,
        (SELECT count(*) FROM currency_revisions WHERE currency_id = 1) AS revisions;
      """
    Then the query result is received
      """
      | usd     | revisions |
      | USD 840 | 1         |
      """

    Examples:
      | field  |
      | code   |
      | number |

  Scenario Outline: Currency is not updated when it is <case>
    Given the HTTP request contains a body from file "testdata/usd_renamed"
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
      | case    | currency_id |
      | deleted | 5           |
      | missing | 100         |

  Scenario Outline: Currency is not updated without a valid user (<case>)
    Given a PATCH HTTP request
    And the HTTP request contains headers
      """
      | Header        | Value           |
      | Authorization | <authorization> |
      """
    And the HTTP request contains a body from file "testdata/usd_renamed"
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
      SELECT name FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | name      |
      | US Dollar |
      """

    Examples:
      | case               | authorization    |
      | token is absent    |                  |
      | token is not a JWT | Bearer not-a-jwt |

  Scenario: Currency is not updated from a malformed body
    Given the HTTP request contains a body
      """
      {"name": "United States Dollar",
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "failed to decode request"
      }
      """

  Scenario: Currency is not updated for a non-numeric currency ID
    Given the HTTP request contains a body from file "testdata/usd_renamed"
    When the HTTP request is sent to "/v1/currencies/abc"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "invalid request parameters"
      }
      """
