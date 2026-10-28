package access_test

import (
	"context"
	"testing"
	"uuid"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

// TestAllowed checks every cell of the role matrix from documents/070.role-matrix.md, section 3.
func TestAllowed(t *testing.T) {
	t.Parallel()

	const (
		c = access.LevelCreate
		r = access.LevelRead
		u = access.LevelUpdate
		x = access.LevelExecute
		d = access.LevelDelete
	)

	levels := []access.Level{c, r, u, x, d}
	groups := []access.Group{access.GroupClassifiers, access.GroupHR, access.GroupRestrictedHR}

	granted := map[string]map[access.Group][]access.Level{
		access.RoleReader: {
			access.GroupClassifiers: {r, x},
			access.GroupHR:          {r, x},
		},
		access.RoleHRReader: {
			access.GroupClassifiers:  {r, x},
			access.GroupHR:           {r, x},
			access.GroupRestrictedHR: {r, x},
		},
		access.RoleAdmin: {
			access.GroupClassifiers: {c, r, u, x, d},
			access.GroupHR:          {r, x},
		},
		access.RoleHRAdmin: {
			access.GroupClassifiers:  {r, x},
			access.GroupHR:           {c, r, u, x, d},
			access.GroupRestrictedHR: {c, r, u, x, d},
		},
		"unknown-role": {},
	}

	for role, byGroup := range granted {
		for _, group := range groups {
			for _, level := range levels {
				want := false
				for _, l := range byGroup[group] {
					if l == level {
						want = true
					}
				}

				assert.Equalf(t, want, access.Allowed([]string{role}, group, level), "role %s, group %s, level %s", role, group, level)
			}
		}
	}
}

func TestAllowedCombinesRoles(t *testing.T) {
	t.Parallel()

	roles := []string{access.RoleAdmin, access.RoleHRAdmin}

	assert.True(t, access.Allowed(roles, access.GroupClassifiers, access.LevelDelete))
	assert.True(t, access.Allowed(roles, access.GroupRestrictedHR, access.LevelCreate))
	assert.False(t, access.Allowed(nil, access.GroupClassifiers, access.LevelRead))
}

func TestAuthorize(t *testing.T) {
	t.Parallel()

	reader := &actor.Actor{
		UserID: uuid.MustParse("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
		Roles:  []string{access.RoleReader},
	}

	testCases := map[string]struct {
		ctx   context.Context
		level access.Level
		want  *actor.Actor
		err   error
	}{
		"allowed": {
			ctx:   actor.WithActor(context.Background(), reader),
			level: access.LevelRead,
			want:  reader,
		},
		"permission denied": {
			ctx:   actor.WithActor(context.Background(), reader),
			level: access.LevelCreate,
			err:   domains.ErrPermissionDenied,
		},
		"unauthenticated": {
			ctx:   context.Background(),
			level: access.LevelRead,
			err:   domains.ErrUnauthenticated,
		},
	}

	for name, tc := range testCases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			got, err := access.Authorize(tc.ctx, access.GroupClassifiers, tc.level)
			if tc.err != nil {
				require.ErrorIs(t, err, tc.err)
				assert.Nil(t, got)

				return
			}

			require.NoError(t, err)
			assert.Equal(t, tc.want, got)
		})
	}
}
