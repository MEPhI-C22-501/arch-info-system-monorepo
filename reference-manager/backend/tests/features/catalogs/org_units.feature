Feature: Organizational units

  Units form a hierarchy through the parent reference, a reference that forms a cycle is rejected (FR-RM-50).

  Background:
    Given the SQL query from file "testdata/hr.sql" is executed

  Scenario: A team is created under a department and listed by its parent
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "dev-frontend", "name": "Frontend team", "kind": "TEAM", "parent_id": 1}
      """
    When the HTTP request is sent to "/v1/org_units/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a body
      """
      {
        "id": 3,
        "code": "dev-frontend",
        "name": "Frontend team",
        "kind": "TEAM",
        "parent_id": 1,
        "is_deleted": false,
        "revision": 1,
        "last_changer": "d81f4b6c-2e9a-4c35-b7d0-6a5e4f3c2b1d",
        "created_at": "{{any}}",
        "updated_at": "{{any}}",
        "deleted_at": "0001-01-01T00:00:00Z"
      }
      """
    Given a GET HTTP request
    And the HTTP request is authorized as "reader"
    And the HTTP request contains URL parameters
      """
      filter=parent_id = 1 AND kind = "TEAM"
      order_by=code
      """
    When the HTTP request is sent to "/v1/org_units/"
    Then an HTTP response is received with status 200
    And the HTTP response contains a value at "/org_units/*/code"
      """
      ["dev-backend", "dev-frontend"]
      """

  Scenario: A unit cannot be moved under its own descendant
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains URL parameters
      """
      updateMask=parent_id
      """
    And the HTTP request contains a body
      """
      {"code": "dev", "name": "Development", "kind": "DEPARTMENT", "parent_id": 2}
      """
    When the HTTP request is sent to "/v1/org_units/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "parent_id", "message": "reference forms a cycle in the hierarchy"}
        ]
      }
      """

  Scenario: A unit cannot be its own parent and the kind is checked
    Given a PATCH HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "dev", "name": "Development", "kind": "DEPARTMENT", "parent_id": 1}
      """
    When the HTTP request is sent to "/v1/org_units/1"
    Then an HTTP response is received with status 400
    And the HTTP response contains a value at "/details/0/field"
      """
      "parent_id"
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "hr-admin"
    And the HTTP request contains a body
      """
      {"code": "ops", "name": "Operations", "kind": "GROUP"}
      """
    When the HTTP request is sent to "/v1/org_units/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "kind", "message": "must be one of DEPARTMENT, TEAM"}
        ]
      }
      """

  Scenario: Grades and project roles keep their own fields
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "senior", "name": "Senior", "rank": 300}
      """
    When the HTTP request is sent to "/v1/grades/"
    Then an HTTP response is received with status 400
    And the HTTP response contains a body
      """
      {
        "message": "validation failed",
        "details": [
          {"field": "rank", "message": "must be at most 100"}
        ]
      }
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "senior", "name": "Senior", "rank": 3}
      """
    When the HTTP request is sent to "/v1/grades/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/rank"
      """
      3
      """
    Given a POST HTTP request
    And the HTTP request is authorized as "admin"
    And the HTTP request contains a body
      """
      {"code": "developer", "name": "Developer", "description": "Implements and reviews code."}
      """
    When the HTTP request is sent to "/v1/project_roles/"
    Then an HTTP response is received with status 201
    And the HTTP response contains a value at "/description"
      """
      "Implements and reviews code."
      """
