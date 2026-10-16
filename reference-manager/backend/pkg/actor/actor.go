package actor

import (
	"context"
	"slices"
	"uuid"
)

// Actor is the authenticated caller of a request: a user or a service account.
type Actor struct {
	UserID uuid.UUID
	Roles  []string
}

// HasRole reports whether the actor has the role.
func (a *Actor) HasRole(role string) bool {
	return slices.Contains(a.Roles, role)
}

type actorKey struct{}

func WithActor(ctx context.Context, a *Actor) context.Context {
	return context.WithValue(ctx, actorKey{}, a)
}

func FromContext(ctx context.Context) (*Actor, bool) {
	a, ok := ctx.Value(actorKey{}).(*Actor)
	return a, ok && a != nil
}

func UserIDFromContext(ctx context.Context) (uuid.UUID, bool) {
	a, ok := FromContext(ctx)
	if !ok {
		return uuid.UUID{}, false
	}

	return a.UserID, true
}
