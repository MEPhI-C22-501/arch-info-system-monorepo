Feature: Currency revision listing

  Background:
    Given the SQL query from file "testdata/currency_revisions.sql" is executed
    And a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """

  Scenario: Revisions of a currency are listed in chronological order by default
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header       | Value            |
      | Content-Type | application/json |
      """
    And the HTTP response contains a value at "/revisions/*/revision_number"
      """
      [1, 2, 3]
      """
    And the HTTP response contains a value at "/revisions/*/currency_id"
      """
      [1, 1, 1]
      """

  Scenario: Revisions are returned page by page
    Given the HTTP request contains URL parameters
      """
      pageSize=2
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revisions/*/revision_number"
      """
      [1, 2]
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
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "revisions": [
          {
            "id": 3,
            "currency_id": 1,
            "revision_number": 3,
            "change": [
              {"op": "replace", "path": "/decimals", "value": 3}
            ],
            "changed_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "changed_at": "2026-10-03T10:00:00Z"
          }
        ]
      }
      """

  Scenario: Page token cannot be used with another currency
    Given the HTTP request contains URL parameters
      """
      pageSize=1
      allowDeleted=true
      """
    And the HTTP request is sent to "/v1/currencies/1/revisions"
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
      allowDeleted=true
      """
    And the HTTP request contains URL parameter "pageToken" from the HTTP response value at "/nextPageToken"
    When the HTTP request is sent to "/v1/currencies/2/revisions"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "invalid pageToken: token does not match the request parameters"
      }
      """

  Scenario Outline: Revisions are filtered by <case>
    Given the HTTP request contains URL parameters
      """
      filter=<filter>
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revisions/*/revision_number"
      """
      <revisions>
      """

    Examples:
      | case               | filter                                                  | revisions |
      | revision number    | revision_number = 2                                     | [2]       |
      | comparison         | revision_number >= 2                                    | [2, 3]    |
      | changer            | changed_by = "3fa85f64-5717-4562-b3fc-2c963f66afa6"     | [1, 3]    |
      | timestamp          | changed_at > "2026-10-01T12:00:00Z"                     | [2, 3]    |
      | timestamp function | changed_at < timestamp("2026-10-02T00:00:00Z")          | [1]       |
      | negation           | NOT revision_number = 1                                 | [2, 3]    |
      | disjunction        | revision_number = 1 OR revision_number = 3              | [1, 3]    |
      | nothing matches    | revision_number > 3                                     | []        |

  Scenario Outline: Revisions are ordered by <order_by>
    Given the HTTP request contains URL parameters
      """
      order_by=<order_by>
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revisions/*/revision_number"
      """
      <revisions>
      """

    Examples:
      | order_by             | revisions |
      | revision_number      | [1, 2, 3] |
      | revision_number desc | [3, 2, 1] |
      | changed_at desc      | [3, 2, 1] |

  Scenario Outline: Revisions of a deleted currency are listed when <case>
    Given the HTTP request contains URL parameters
      """
      allowDeleted=<allow_deleted>
      """
    When the HTTP request is sent to "/v1/currencies/2/revisions"
    Then an HTTP response is received with status <status>
    And the HTTP response contains a value at "<pointer>"
      """
      <value>
      """

    Examples:
      | case                     | allow_deleted | status | pointer                       | value                |
      | deleted ones are allowed | true          | 200    | /revisions/*/revision_number  | [1, 2]               |
      | deleted ones are hidden  | false         | 404    | /message                      | "currency not found" |

  Scenario: Revisions of a missing currency are not found
    When the HTTP request is sent to "/v1/currencies/3/revisions"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body from file "testdata/not_found"

  Scenario Outline: Revisions are not listed for an invalid <case>
    Given the HTTP request contains URL parameters
      """
      <parameter>
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "<message>"
      }
      """

    Examples:
      | case               | parameter                    | message                                                                                      |
      | filter field       | filter=code = "USD"          | invalid filter: check call expr: undeclared identifier 'code'                                |
      | filter syntax      | filter=revision_number =     | invalid filter: syntax error at 1:18: unexpected end of filter                               |
      | filter type        | filter=revision_number = "x" | invalid filter: check call expr: no matching overload found for calling '=' with [primitive:INT64 primitive:STRING] |
      | ordering field     | order_by=changed_by          | invalid order_by: invalid field path: changed_by                                             |
      | page token         | pageToken=garbage            | invalid pageToken: malformed token                                                           |
      | page size          | pageSize=-1                  | invalid pageSize: must not be negative                                                       |
      | page size format   | pageSize=many                | invalid request parameters                                                                   |
      | allowDeleted       | allowDeleted=maybe           | invalid request parameters                                                                   |

  Scenario Outline: Revisions are not listed without a valid user (<case>)
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    When the HTTP request is sent to "/v1/currencies/1/revisions"
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
