Feature: Countries

  Countries are a shared classifier: every role reads and exports them, only reference-admin changes them.
  A country may reference its main currency.

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed

  Scenario: A country is created with the first revision and read back
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia", "currency_id": 1}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a body
      """
      {
        "id": 1,
        "alpha2": "RU",
        "alpha3": "RUS",
        "numeric_code": "643",
        "name": "Russia",
        "currency_id": 1,
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
      SELECT country_id, revision_number FROM country_revisions;
      """
    Then the query result is received
      """
      | country_id | revision_number |
      | 1          | 1               |
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/countries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/alpha3"
      """
      "RUS"
      """

  Scenario: Invalid fields are reported together with the field names
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "ru", "alpha3": "RUS", "numeric_code": "64", "name": "Russia", "currency_id": 99}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "alpha2", "message": "must match ^[A-Z]{2}$"},
          {"field": "numeric_code", "message": "must be at least 3 characters long"}
        ]
      }
      """

  Scenario: A reference to a missing currency is rejected
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia", "currency_id": 99}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "currency_id", "message": "currencies 99 does not exist"}
        ]
      }
      """

  Scenario: Unique codes are rejected with a conflict
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia"}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUX", "numeric_code": "644", "name": "Other"}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 409
    And the HTTP response contains a body
      """
      {"message": "country already exists"}
      """

  Scenario: Only the fields of the update mask change and the change is recorded
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia"}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    Given a PATCH HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains URL parameters
      """
      updateMask=name,currency_id
      """
    And the HTTP request contains a body
      """
      {"alpha2": "XX", "alpha3": "XXX", "numeric_code": "000", "name": "Russian Federation", "currency_id": 1}
      """
    When the HTTP request is sent to "/v1/countries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/alpha2"
      """
      "RU"
      """
    And the HTTP response contains a value at "/name"
      """
      "Russian Federation"
      """
    And the HTTP response contains a value at "/revision"
      """
      2
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/countries/1/revisions/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/change"
      """
      [
        {"op": "replace", "path": "/currency_id", "value": 1},
        {"op": "replace", "path": "/name", "value": "Russian Federation"}
      ]
      """

  Scenario: A deleted country disappears from the list until deleted records are allowed
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia"}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    Given a DELETE HTTP request
    And the HTTP request is authorized as "admin"
    When the HTTP request is sent to "/v1/countries/1"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/is_deleted"
      """
      true
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "admin"
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {"countries": []}
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains URL parameters
      """
      allowDeleted=true
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/countries/*/alpha2"
      """
      ["RU"]
      """

  Scenario: Countries are listed with a filter and exported to an Excel file
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "RU", "alpha3": "RUS", "numeric_code": "643", "name": "Russia", "currency_id": 1}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"alpha2": "KZ", "alpha3": "KAZ", "numeric_code": "398", "name": "Kazakhstan"}
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 201
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=name : "kazakh"
      order_by=alpha2
      """
    When the HTTP request is sent to "/v1/countries/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/countries/*/alpha2"
      """
      ["KZ"]
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/countries/export"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header              | Value                                                             |
      | Content-Type        | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
      | Content-Disposition | attachment; filename=countries.xlsx                               |
      """
    And the HTTP response contains an Excel sheet "Countries" with rows
      """
      | Alpha2 | Alpha3 | Numeric code | Name       | Currency id | Revision |
      | RU     | RUS    | 643          | Russia     | 1           | 1        |
      | KZ     | KAZ    | 398          | Kazakhstan |             | 1        |
      """
