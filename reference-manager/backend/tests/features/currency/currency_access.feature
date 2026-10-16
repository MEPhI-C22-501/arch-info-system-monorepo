Feature: Access to currencies

  Currencies belong to the shared classifiers: every role of the service reads and exports them,
  only reference-admin changes them (documents/070.role-matrix.md). Tokens are issued by Keycloak.

  Background:
    Given the SQL query from file "testdata/currencies.sql" is executed

  Scenario Outline: Currencies are read and exported by <user>
    Given a GET HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 200
    Given a GET HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/currencies/1/revisions"
    Then an HTTP response is received with status 200
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/currencies/export"
    Then an HTTP response is received with status 200

    Examples:
      | user      |
      | reader    |
      | hr-reader |
      | admin     |
      | hr-admin  |

  Scenario Outline: Currency is not created by <user>
    Given a POST HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains a body
      """
      {
        "code": "XAU",
        "number": "959",
        "name": "Gold",
        "decimals": 0,
        "is_deleted": false
      }
      """
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 403
    And the HTTP response contains a body
      """
      {
        "message": "permission denied"
      }
      """
    When the SQL query is executed
      """
      SELECT count(*) AS currencies FROM currencies WHERE code = 'XAU';
      """
    Then the query result is received
      """
      | currencies |
      | 0          |
      """

    Examples:
      | user      |
      | reader    |
      | hr-reader |
      | hr-admin  |

  Scenario Outline: Currency is not changed by <user>
    Given a PATCH HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains a body from file "testdata/usd_renamed"
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 403
    Given a DELETE HTTP request
    And the HTTP request is authorized as "<user>"
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 403
    Given a DELETE HTTP request
    And the HTTP request is authorized as "<user>"
    And the HTTP request contains URL parameters
      """
      force=true
      """
    When the HTTP request is sent to "/v1/currencies/1"
    Then an HTTP response is received with status 403
    When the SQL query is executed
      """
      SELECT name, is_deleted, (SELECT count(*) FROM currency_revisions WHERE currency_id = 1) AS revisions
      FROM currencies WHERE id = 1;
      """
    Then the query result is received
      """
      | name      | is_deleted | revisions |
      | US Dollar | f          | 1         |
      """

    Examples:
      | user     |
      | reader   |
      | hr-admin |

  Scenario: Currencies are not read by a user without roles of the service
    Given a GET HTTP request
    And the HTTP request is authorized as "outsider"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 403
    And the HTTP response contains a body
      """
      {
        "message": "permission denied"
      }
      """

  Scenario: Token issued for another audience is rejected
    Given a GET HTTP request
    And the HTTP request is authorized as "admin" through the client "foreign-app"
    When the HTTP request is sent to "/v1/currencies/"
    Then an HTTP response is received with status 401
    And the HTTP response contains headers
      """
      | Header           | Value                        |
      | WWW-Authenticate | Bearer error="invalid_token" |
      """
    And the HTTP response contains a body
      """
      {
        "message": "unauthenticated"
      }
      """

  Scenario Outline: Request with <case> is rejected
    Given a GET HTTP request
    And the HTTP request contains headers
      """
      | Header        | Value           |
      | Authorization | <authorization> |
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
      | case                         | authorization                                                                                       |
      | a token of an unknown key    | Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6InVua25vd24ifQ.eyJzdWIiOiIzZmE4NWY2NCJ9.c2lnbmF0dXJl            |
      | an unsigned token            | Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiIzZmE4NWY2NC01NzE3LTQ1NjItYjNmYy0yYzk2M2Y2NmFmYTYifQ.         |
      | basic credentials            | Basic YWRtaW46YWRtaW4=                                                                              |

  Scenario: Health endpoints are available without a token
    Given a GET HTTP request
    When the HTTP request is sent to "/v1/health/livez"
    Then an HTTP response is received with status 200
