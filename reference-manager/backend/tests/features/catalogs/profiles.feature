Feature: Profiles of accounts

  A profile joins a Keycloak account with the employee linked to it. Every signed-in account reads its own profile,
  a new account has no roles of the service (ADR-024). The profiles of other people need the profile role or read
  access to HR references. An account linked to an employee has one profile, the employee profile.

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed

  Scenario: An account without roles of the service reads its own employee profile
    Given the SQL query is executed
      """
      UPDATE employees SET account_user_id = 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', account_state = 'ENABLED' WHERE id = 1;
      """
    And a GET HTTP request
    And the HTTP request is authorized as "outsider"
    When the HTTP request is sent to "/v1/profiles/me"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "issuer": "http://localhost:8183/realms/arch-info-system",
        "employeeId": 1,
        "userId": "f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c",
        "displayName": "Ivanov Ivan Ivanovich",
        "workEmail": "i.ivanov@example.org",
        "orgUnitId": null,
        "orgUnitName": null,
        "positionId": null,
        "positionName": null,
        "employmentState": "EMPLOYED",
        "accountState": "ENABLED",
        "isDeleted": false,
        "isTechnical": false,
        "isActive": true,
        "updatedAt": "{{any}}"
      }
      """

  Scenario: An account without an employee reads its account profile
    Given the SQL query is executed
      """
      INSERT INTO user_profiles (issuer, subject, display_name, work_email)
      VALUES ('http://localhost:8183/realms/arch-info-system', 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', 'Outside contractor', 'contractor@example.org');
      """
    And a GET HTTP request
    And the HTTP request is authorized as "outsider"
    When the HTTP request is sent to "/v1/profiles/me"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/employeeId"
      """
      null
      """
    And the HTTP response contains a value at "/displayName"
      """
      "Outside contractor"
      """

  Scenario: An account without a profile gets not found
    Given a GET HTTP request
    And the HTTP request is authorized as "outsider"
    When the HTTP request is sent to "/v1/profiles/me"
    Then an HTTP response is received with status 404
    And the HTTP response contains a body
      """
      {"message": "profile not found"}
      """

  Scenario: An account without roles of the service cannot read the profiles of other people
    Given a GET HTTP request
    And the HTTP request is authorized as "outsider"
    When the HTTP request is sent to "/v1/profiles"
    Then an HTTP response is received with status 403
    And the HTTP response contains a body
      """
      {"message": "permission denied", "details": [{"field": "role", "message": "read access to the profiles of other accounts needs one of the roles: reference-profile-reader, reference-admin, reference-hr-admin, reference-hr-reader, reference-reader"}]}
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "outsider"
    And the HTTP request contains a body
      """
      {"keys": [{"kind": "employeeId", "id": "1"}]}
      """
    When the HTTP request is sent to "/v1/profiles/resolve"
    Then an HTTP response is received with status 403

  Scenario: Profiles are resolved by keys in the order of the request, a missing profile is null
    Given the SQL query is executed
      """
      UPDATE employees SET account_user_id = 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', account_state = 'ENABLED' WHERE id = 1;
      """
    And a POST HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains a body
      """
      {"keys": [{"kind": "userId", "id": "0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e"}, {"kind": "employeeId", "id": "1"}, {"kind": "userId", "id": "f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c"}]}
      """
    When the HTTP request is sent to "/v1/profiles/resolve"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/items/0/profile"
      """
      null
      """
    And the HTTP response contains a value at "/items/1/profile/employeeId"
      """
      1
      """
    And the HTTP response contains a value at "/items/2/key"
      """
      {"kind": "userId", "id": "f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c"}
      """
    And the HTTP response contains a value at "/items/2/profile/displayName"
      """
      "Ivanov Ivan Ivanovich"
      """

  Scenario: An account linked to an employee has one profile and a technical account is left out of the list
    Given the SQL query is executed
      """
      UPDATE employees SET account_user_id = 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', account_state = 'ENABLED' WHERE id = 1;
      INSERT INTO user_profiles (issuer, subject, display_name, is_technical)
      VALUES ('http://localhost:8183/realms/arch-info-system', 'f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c', 'Account of Ivanov', FALSE),
             ('http://localhost:8183/realms/arch-info-system', '0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e', 'CI robot', TRUE);
      """
    And a GET HTTP request
    And the HTTP request is authorized as "reader"
    When the HTTP request is sent to "/v1/profiles"
    Then an HTTP response is received with status 200
    And the HTTP response contains a body
      """
      {
        "items": [
          {
            "issuer": "http://localhost:8183/realms/arch-info-system",
            "employeeId": 1,
            "userId": "f7a6b5c4-d3e2-4f1a-8b9c-1d2e3f4a5b6c",
            "displayName": "Ivanov Ivan Ivanovich",
            "orgUnitId": null,
            "orgUnitName": null,
            "positionId": null,
            "positionName": null,
            "employmentState": "EMPLOYED",
            "accountState": "ENABLED",
            "isDeleted": false,
            "isTechnical": false,
            "isActive": true,
            "updatedAt": "{{any}}"
          }
        ]
      }
      """
