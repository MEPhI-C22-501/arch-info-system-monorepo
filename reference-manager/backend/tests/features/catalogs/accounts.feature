Feature: Employee accounts in Keycloak

  A hired employee gets a Keycloak account that is enabled while the employee works, the dismissal blocks it,
  the names and the email follow the record, a working employee with an account cannot be deleted,
  SyncAccount repeats the operation without a second account (FR-RM-53..58).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed
    And the Keycloak account "m.petrova" is removed
    And the Keycloak account "i.ivanov" is removed

  Scenario: A hired employee gets an enabled account with the reader role
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/account_state"
      """
      "ENABLED"
      """
    And the HTTP response contains a value at "/account_user_id"
      """
      "{{any}}"
      """
    And the HTTP response contains a value at "/revision"
      """
      2
      """
    And the Keycloak account "m.petrova" is enabled
    And the Keycloak account "m.petrova" has email "m.petrova@example.org"
    And the Keycloak account "m.petrova" has the realm role "reference-reader"
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/employees/2/revisions/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/change/0/path"
      """
      "/account_state"
      """

  Scenario: The dismissal blocks the account and keeps the link
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"dismissal_date": "2026-12-31"}
      """
    When the HTTP request is sent to "/v1/employees/2/dismiss"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employment_state"
      """
      "DISMISSED"
      """
    And the HTTP response contains a value at "/account_state"
      """
      "DISABLED"
      """
    And the HTTP response contains a value at "/account_user_id"
      """
      "{{any}}"
      """
    And the Keycloak account "m.petrova" is disabled

  Scenario: A working employee with an account cannot be deleted
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    Given a DELETE HTTP request
    And the HTTP request is authorized as "hr-admin"
    When the HTTP request is sent to "/v1/employees/2"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "employee 2 has an account, dismiss the employee before the deletion: failed precondition"}
      """

  Scenario: A changed email reaches the account
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=email
      """
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "maria.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/account_state"
      """
      "ENABLED"
      """
    And the Keycloak account "m.petrova" has email "maria.petrova@example.org"

  Scenario: An account left by an interrupted creation is adopted, a second one is not created
    Given a Keycloak account "m.petrova" exists with email "m.petrova@example.org"
    And a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/account_state"
      """
      "ENABLED"
      """
    And the Keycloak account "m.petrova" is enabled

  Scenario: A username taken by a foreign account is rejected and the record stays PENDING
    Given a Keycloak account "m.petrova" exists with email "someone.else@example.org"
    And a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"personnel_number": "1024", "family_name": "Petrova", "given_name": "Maria", "email": "m.petrova@example.org", "username": "m.petrova", "hire_date": "2026-11-02"}
      """
    When the HTTP request is sent to "/v1/employees/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {"message": "employee 2: account conflict: username \"m.petrova\" belongs to another account: failed precondition"}
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "hr-admin"
    When the HTTP request is sent to "/v1/employees/2"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/account_state"
      """
      "PENDING"
      """

  Scenario: An employee loaded without an account gets one by SyncAccount
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    When the HTTP request is sent to "/v1/employees/1/syncAccount"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/account_state"
      """
      "ENABLED"
      """
    And the Keycloak account "i.ivanov" is enabled
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    When the HTTP request is sent to "/v1/employees/1/syncAccount"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/revision"
      """
      2
      """

  Scenario: Only HR administrators repeat the operation with the account
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    When the HTTP request is sent to "/v1/employees/1/syncAccount"
    Then an HTTP response is received with status 403
