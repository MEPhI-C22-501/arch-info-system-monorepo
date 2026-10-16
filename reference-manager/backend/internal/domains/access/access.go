// Package access implements the role matrix of the service (documents/070.role-matrix.md):
// an operation is allowed when one of the caller roles grants the access level on the group of the reference.
package access

import (
	"context"
	"fmt"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

// Group is a group of references sharing access rules.
type Group string

const (
	// GroupClassifiers holds the shared classifiers: currencies, countries, project roles, grades.
	GroupClassifiers Group = "classifiers"
	// GroupHR holds the HR references: employees, org units, positions, assignments.
	GroupHR Group = "hr"
	// GroupRestrictedHR holds salaries and absences, which are readable only by the HR roles.
	GroupRestrictedHR Group = "restricted-hr"
)

// Level is an access level an operation requires.
type Level string

const (
	LevelCreate  Level = "create"
	LevelRead    Level = "read"
	LevelUpdate  Level = "update"
	LevelExecute Level = "execute"
	LevelDelete  Level = "delete"
)

// Roles of the service, they come from the Keycloak access token.
const (
	RoleReader   = "reference-reader"
	RoleHRReader = "reference-hr-reader"
	RoleAdmin    = "reference-admin"
	RoleHRAdmin  = "reference-hr-admin"
)

var (
	readLevels = []Level{LevelRead, LevelExecute}
	allLevels  = []Level{LevelCreate, LevelRead, LevelUpdate, LevelExecute, LevelDelete}
)

// matrix grants access levels to roles per group, a role missing in a group has no access to it.
var matrix = map[string]map[Group][]Level{
	RoleReader: {
		GroupClassifiers: readLevels,
		GroupHR:          readLevels,
	},
	RoleHRReader: {
		GroupClassifiers:  readLevels,
		GroupHR:           readLevels,
		GroupRestrictedHR: readLevels,
	},
	RoleAdmin: {
		GroupClassifiers: allLevels,
		GroupHR:          readLevels,
	},
	RoleHRAdmin: {
		GroupClassifiers:  readLevels,
		GroupHR:           allLevels,
		GroupRestrictedHR: allLevels,
	},
}

// Allowed reports whether any of the roles grants the level on the group, the rights of several roles are combined.
func Allowed(roles []string, group Group, level Level) bool {
	for _, role := range roles {
		for _, granted := range matrix[role][group] {
			if granted == level {
				return true
			}
		}
	}

	return false
}

// Authorize returns the actor of the context when it may perform an operation of the level on the group.
// It fails with domains.ErrUnauthenticated without an actor and with domains.ErrPermissionDenied without the level.
func Authorize(ctx context.Context, group Group, level Level) (*actor.Actor, error) {
	a, ok := actor.FromContext(ctx)
	if !ok {
		return nil, domains.ErrUnauthenticated
	}

	if !Allowed(a.Roles, group, level) {
		return nil, fmt.Errorf("%s access to %s references: %w", level, group, domains.ErrPermissionDenied)
	}

	return a, nil
}
