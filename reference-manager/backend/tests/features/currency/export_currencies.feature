Feature: Currency export

  Background:
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """

  Scenario: Active currencies are exported to an Excel file in creation order
    Given the SQL query from file "testdata/currencies.sql" is executed
    When the HTTP request is sent to "/v1/currencies/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header              | Value                                                             |
      | Content-Type        | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
      | Content-Disposition | attachment; filename=currencies.xlsx                              |
      """
    And the HTTP response contains an Excel sheet "Currencies" with rows
      """
      | Code | Number | Name              | Decimals | Revision | Last changer                         | Created at          | Updated at          |
      | USD  | 840    | US Dollar         | 2        | 1        | 3fa85f64-5717-4562-b3fc-2c963f66afa6 | 2026-10-01 10:00:00 | 2026-10-01 10:00:00 |
      | EUR  | 978    | Euro              | 2        | 1        | 3fa85f64-5717-4562-b3fc-2c963f66afa6 | 2026-10-02 10:00:00 | 2026-10-02 10:00:00 |
      | JPY  | 392    | Yen               | 0        | 1        | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c | 2026-10-03 10:00:00 | 2026-10-03 10:00:00 |
      | BHD  | 048    | Bahraini Dinar    | 3        | 1        | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c | 2026-10-04 10:00:00 | 2026-10-04 10:00:00 |
      | CLF  | 990    | Unidad de Fomento | 4        | 1        | 3fa85f64-5717-4562-b3fc-2c963f66afa6 | 2026-10-07 10:00:00 | 2026-10-07 10:00:00 |
      """

  Scenario: Export reflects changes made through the API
    Given the SQL query from file "testdata/currencies.sql" is executed
    And a PATCH HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 9b2e4c1a-7d3f-4e8a-b5c6-1f0a2d3e4b5c |
      """
    And the HTTP request contains URL parameters
      """
      updateMask=name
      """
    And the HTTP request contains a body
      """
      {
        "code": "JPY",
        "number": "392",
        "name": "Japanese Yen",
        "decimals": 0,
        "is_deleted": false
      }
      """
    And the HTTP request is sent to "/v1/currencies/3"
    And an HTTP response is received with status 200
    And a DELETE HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    And the HTTP request is sent to "/v1/currencies/2"
    And an HTTP response is received with status 200
    And a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value                                |
      | X-User-ID | 3fa85f64-5717-4562-b3fc-2c963f66afa6 |
      """
    When the HTTP request is sent to "/v1/currencies/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains an Excel sheet "Currencies" with rows
      """
      | Code | Number | Name              | Decimals | Revision |
      | USD  | 840    | US Dollar         | 2        | 1        |
      | JPY  | 392    | Japanese Yen      | 0        | 2        |
      | BHD  | 048    | Bahraini Dinar    | 3        | 1        |
      | CLF  | 990    | Unidad de Fomento | 4        | 1        |
      """

  Scenario: Export of an empty reference contains only the header
    When the HTTP request is sent to "/v1/currencies/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains an Excel sheet "Currencies" with rows
      """
      | Code | Number | Name | Decimals | Revision | Last changer | Created at | Updated at |
      """

  Scenario Outline: Currencies are not exported without a valid user (<case>)
    Given a POST HTTP request
    And the HTTP request contains headers
      """
      | Header    | Value     |
      | X-User-ID | <user_id> |
      """
    When the HTTP request is sent to "/v1/currencies/export"
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
