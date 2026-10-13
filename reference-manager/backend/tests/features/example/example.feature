Feature: Example Feature

  Scenario: First example scenario using HTTP steps and SQL steps
    Given a GET HTTP request
    And the HTTP request contains URL parameters
      """
      page=1
      limit=20
      status=active
      """
    And the HTTP request contains headers
      """
      | Header | Value |
      |        |       |
      """
    And the HTTP request contains a body
      """
      {
        "hello": "world"
      }
      """
    When the HTTP request is sent to "/v1/example"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header | Value |
      |        |       |
      """
    And the HTTP response contains a body
      """
      {
        "hello": "there"
      }
      """
    When the SQL query is executed
      """
      SELECT * FROM table;
      """
    Then the query result is received
      """
      | id | name |
      |    |      |
      """

  Scenario: Second example scenario using HTTP steps and SQL steps
    Given a GET HTTP request
    And the HTTP request contains URL parameters
      """
      page=1
      limit=20
      status=active
      """
    And the HTTP request contains headers
      """
      | Header | Value |
      |        |       |
      """
    And the HTTP request contains a body from file "/relative/path/to/testdata/request"
    When the HTTP request is sent to "/v1/example"
    Then an HTTP response is received with status 200
    And the HTTP response contains headers
      """
      | Header | Value |
      |        |       |
      """
    And the HTTP response contains a body from file "/relative/path/to/testdata/response"
    When the SQL query from file "testdata/queries/find-users.sql" is executed
    Then the query result matches file "testdata/countries.csv"