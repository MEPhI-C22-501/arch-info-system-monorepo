Feature: Currency listing

  Background:
    Given the SQL query from file "testdata/currencies.sql" is executed
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """

  Scenario: Active currencies are listed in creation order by default
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a value at "/currencies/*/code"
      """
      ["USD", "EUR", "JPY", "BHD", "CLF"]
      """

  Scenario: Currencies are returned page by page
    Given the HTTP request contains URL parameters
      """
      pageSize=2
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body from file "testdata/currencies_first_page"
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains URL parameters
      """
      pageSize=2
      """
    And the HTTP request contains URL parameter "pageToken" from the HTTP response value at "/nextPageToken"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/currencies/*/code"
      """
      ["JPY", "BHD"]
      """
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains URL parameters
      """
      pageSize=2
      """
    And the HTTP request contains URL parameter "pageToken" from the HTTP response value at "/nextPageToken"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "currencies": [
          {
            "code": "CLF",
            "number": "990",
            "name": "Unidad de Fomento",
            "decimals": 4,
            "is_deleted": false,
            "revision": 1,
            "last_changer": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "created_at": "2026-10-07T10:00:00Z",
            "updated_at": "2026-10-07T10:00:00Z",
            "deleted_at": "0001-01-01T00:00:00Z"
          }
        ]
      }
      """

  Scenario: Page token cannot be used with another filter
    Given the HTTP request contains URL parameters
      """
      pageSize=1
      """
    And the HTTP request is sent to "/v1/currencies/"
    And an HTTP response is received with status 200
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request contains URL parameters
      """
      pageSize=1
      filter=decimals = 2
      """
    And the HTTP request contains URL parameter "pageToken" from the HTTP response value at "/nextPageToken"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "invalid pageToken: token does not match the request parameters"
      }
      """

  Scenario Outline: Currencies are filtered by <case>
    Given the HTTP request contains URL parameters
      """
      filter=<filter>
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/currencies/*/code"
      """
      <codes>
      """

    Examples:
      | case                     | filter                                                  | codes                        |
      | equality                 | code = "USD"                                            | ["USD"]                      |
      | inequality               | decimals != 2                                           | ["JPY", "BHD", "CLF"]        |
      | comparison               | decimals >= 3                                           | ["BHD", "CLF"]               |
      | string comparison        | code < "EUR"                                            | ["BHD", "CLF"]               |
      | containment              | name:"DOLLAR"                                           | ["USD"]                      |
      | suffix wildcard          | name = "*o"                                             | ["EUR", "CLF"]               |
      | prefix wildcard          | name = "U*"                                             | ["USD", "CLF"]               |
      | conjunction              | decimals = 2 AND code != "USD"                          | ["EUR"]                      |
      | disjunction              | code = "USD" OR code = "JPY"                            | ["USD", "JPY"]               |
      | negation                 | NOT decimals = 2                                        | ["JPY", "BHD", "CLF"]        |
      | negation shorthand       | -decimals = 2                                           | ["JPY", "BHD", "CLF"]        |
      | grouping                 | (code = "USD" OR code = "JPY") AND decimals = 0         | ["JPY"]                      |
      | timestamp                | created_at >= "2026-10-03T00:00:00Z"                    | ["JPY", "BHD", "CLF"]        |
      | timestamp function       | created_at < timestamp("2026-10-02T00:00:00Z")          | ["USD"]                      |
      | last changer             | last_changer = "9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c"   | ["JPY", "BHD"]               |
      | nothing matches          | code = "XXX"                                            | []                           |

  Scenario Outline: Currencies are ordered by <order_by>
    Given the HTTP request contains URL parameters
      """
      order_by=<order_by>
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/currencies/*/code"
      """
      <codes>
      """

    Examples:
      | order_by             | codes                                   |
      | code                 | ["BHD", "CLF", "EUR", "JPY", "USD"]     |
      | code desc            | ["USD", "JPY", "EUR", "CLF", "BHD"]     |
      | decimals desc, code  | ["CLF", "BHD", "EUR", "USD", "JPY"]     |
      | decimals, name desc  | ["JPY", "USD", "EUR", "BHD", "CLF"]     |
      | created_at desc      | ["CLF", "BHD", "JPY", "EUR", "USD"]     |

  Scenario Outline: Deleted currencies are listed when <case>
    Given the HTTP request contains URL parameters
      """
      allowDeleted=true
      filter=<filter>
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/currencies/*/code"
      """
      <codes>
      """

    Examples:
      | case                        | filter          | codes                                      |
      | they are allowed            |                 | ["USD", "EUR", "JPY", "BHD", "RUR", "CLF"] |
      | only deleted ones are asked | is_deleted      | ["RUR"]                                    |
      | they have a deletion time   | deleted_at:*    | ["RUR"]                                    |
      | they are compared with bool | is_deleted = true | ["RUR"]                                  |

  Scenario Outline: Currencies are not listed for an invalid <case>
    Given the HTTP request contains URL parameters
      """
      <parameter>
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "<message>"
      }
      """

    Examples:
      | case               | parameter                | message                                                                                      |
      | filter field       | filter=status = "ACTIVE" | invalid filter: check call expr: undeclared identifier 'status'                              |
      | filter syntax      | filter=code =            | invalid filter: syntax error at 1:7: unexpected end of filter                                |
      | filter string      | filter=code = "USD       | invalid filter: syntax error at 1:8: unterminated string                                     |
      | filter parenthesis | filter=(code = "USD"     | invalid filter: syntax error at 1:14: expected )                                             |
      | filter type        | filter=decimals = "two"  | invalid filter: check call expr: no matching overload found for calling '=' with [primitive:INT64 primitive:STRING] |
      | filter timestamp   | filter=created_at > "now" | invalid filter: check call expr: invalid timestamp. Should be in RFC3339 format             |
      | ordering field     | order_by=status          | invalid order_by: invalid field path: status                                                 |
      | ordering direction | order_by=code upward     | invalid order_by: unmarshal order by 'code upward': invalid format                           |
      | page token         | pageToken=garbage        | invalid pageToken: malformed token                                                           |
      | page size          | pageSize=-1              | invalid pageSize: must not be negative                                                       |
      | page size format   | pageSize=many            | invalid request parameters                                                                   |

  Scenario Outline: Currencies are not listed without a valid user (<case>)
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    When the HTTP request is sent to "/v1/currencies/"
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
