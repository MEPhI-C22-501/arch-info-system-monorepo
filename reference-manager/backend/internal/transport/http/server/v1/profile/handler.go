package profile

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"
	"uuid"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/render"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/access"
	postgresrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/actor"
)

const reader = "reference-profile-reader"
const limit = 100

type profile struct {
	key             string
	Issuer          string     `json:"issuer"`
	EmployeeID      *int64     `json:"employeeId"`
	UserID          *string    `json:"userId"`
	DisplayName     string     `json:"displayName"`
	WorkEmail       *string    `json:"workEmail,omitempty"`
	OrgUnitID       *int64     `json:"orgUnitId"`
	OrgUnitName     *string    `json:"orgUnitName"`
	PositionID      *int64     `json:"positionId"`
	PositionName    *string    `json:"positionName"`
	EmploymentState *string    `json:"employmentState"`
	AccountState    *string    `json:"accountState"`
	IsDeleted       bool       `json:"isDeleted"`
	IsTechnical     bool       `json:"isTechnical"`
	IsActive        bool       `json:"isActive"`
	UpdatedAt       *time.Time `json:"updatedAt"`
}

type handler struct {
	db     postgresrepo.DB
	issuer string
	log    *slog.Logger
}

func Mount(r chi.Router, db postgresrepo.DB, issuer string, log *slog.Logger) {
	h := handler{db: db, issuer: issuer, log: log}
	r.Get("/v1/profiles/me", h.me)
	r.Get("/v1/profiles", h.list)
	r.Post("/v1/profiles/resolve", h.resolve)
}

const profiles = `
WITH profiles AS (
    SELECT * FROM v_employee_profile
    UNION ALL
    SELECT 'u:' || subject::text, NULL AS employee_id, subject::text, display_name, work_email,
           NULL AS org_unit_id, NULL AS org_unit_name, NULL AS position_id, NULL AS position_name,
           NULL AS employment_state, NULL AS account_state, FALSE, is_technical, is_active, updated_at
    FROM user_profiles u
    WHERE issuer = $1 AND NOT EXISTS (
        SELECT 1 FROM employees e WHERE e.account_user_id = u.subject::text
    )
)
SELECT * FROM profiles
`

func (h handler) read(w http.ResponseWriter, r *http.Request, where string, args ...any) ([]profile, bool) {
	values := append([]any{h.issuer}, args...)
	rows, err := h.db.Querier(r.Context()).Query(r.Context(), profiles+where, values...)
	if err != nil {
		h.failure(w, r, err)
		return nil, false
	}
	defer rows.Close()

	result := []profile{}
	for rows.Next() {
		p := profile{Issuer: h.issuer}
		err := rows.Scan(&p.key, &p.EmployeeID, &p.UserID, &p.DisplayName, &p.WorkEmail,
			&p.OrgUnitID, &p.OrgUnitName, &p.PositionID, &p.PositionName, &p.EmploymentState,
			&p.AccountState, &p.IsDeleted, &p.IsTechnical, &p.IsActive, &p.UpdatedAt)
		if err != nil {
			h.failure(w, r, err)
			return nil, false
		}
		result = append(result, p)
	}
	if err := rows.Err(); err != nil {
		h.failure(w, r, err)
		return nil, false
	}
	return result, true
}

func (h handler) failure(w http.ResponseWriter, r *http.Request, err error) {
	h.log.ErrorContext(r.Context(), "read profiles", slog.String("error", err.Error()))
	problem(w, r, http.StatusServiceUnavailable, "profiles unavailable")
}

func problem(w http.ResponseWriter, r *http.Request, status int, message string) {
	render.Status(r, status)
	render.JSON(w, r, map[string]string{"message": message})
}

func (h handler) authorize(w http.ResponseWriter, r *http.Request) *actor.Actor {
	w.Header().Set("Cache-Control", "no-store")
	a, ok := actor.FromContext(r.Context())
	if !ok {
		problem(w, r, http.StatusUnauthorized, "unauthenticated")
		return nil
	}
	if !a.HasRole(reader) && !access.Allowed(a.Roles, access.GroupHR, access.LevelRead) {
		problem(w, r, http.StatusForbidden, "forbidden")
		return nil
	}
	return a
}

func (h handler) me(w http.ResponseWriter, r *http.Request) {
	a := h.authorize(w, r)
	if a == nil {
		return
	}
	found, ok := h.read(w, r, "WHERE user_id = $2 AND NOT is_technical", a.UserID.String())
	if !ok {
		return
	}
	if len(found) == 0 {
		problem(w, r, http.StatusNotFound, "profile not found")
		return
	}
	render.JSON(w, r, found[0])
}

func (h handler) list(w http.ResponseWriter, r *http.Request) {
	if h.authorize(w, r) == nil {
		return
	}
	params := r.URL.Query()
	size := 50
	if value := params.Get("pageSize"); value != "" {
		parsed, err := strconv.Atoi(value)
		if err != nil || parsed < 1 || parsed > limit {
			problem(w, r, http.StatusBadRequest, "pageSize must be between 1 and 100")
			return
		}
		size = parsed
	}
	after, err := base64.RawURLEncoding.DecodeString(params.Get("pageToken"))
	query := strings.TrimSpace(params.Get("q"))
	if err != nil || len(after) > 40 || len([]rune(query)) > 120 || strings.ContainsRune(query, 0) || bytes.ContainsRune(after, 0) {
		problem(w, r, http.StatusBadRequest, "invalid page token or search")
		return
	}
	includeInactive := params.Get("includeInactive")
	if includeInactive != "" && includeInactive != "true" && includeInactive != "false" {
		problem(w, r, http.StatusBadRequest, "invalid includeInactive")
		return
	}
	found, ok := h.read(w, r, `
WHERE profile_key COLLATE "C" > $2 AND (is_active AND NOT is_technical OR $3)
  AND strpos(lower(display_name), lower($4)) > 0
ORDER BY profile_key COLLATE "C" LIMIT $5`, string(after), includeInactive == "true", query, size+1)
	if !ok {
		return
	}
	next := ""
	if len(found) > size {
		found = found[:size]
		next = base64.RawURLEncoding.EncodeToString([]byte(found[size-1].key))
	}
	for i := range found {
		found[i].WorkEmail = nil
	}
	render.JSON(w, r, struct {
		Items []profile `json:"items"`
		Next  string    `json:"nextPageToken,omitempty"`
	}{found, next})
}

type key struct {
	Kind string `json:"kind"`
	ID   string `json:"id"`
}

func (h handler) resolve(w http.ResponseWriter, r *http.Request) {
	if h.authorize(w, r) == nil {
		return
	}
	var body struct {
		Keys []key `json:"keys"`
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 16384))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&body) != nil || len(body.Keys) == 0 || len(body.Keys) > limit || decoder.Decode(new(any)) != io.EOF {
		problem(w, r, http.StatusBadRequest, "expected between 1 and 100 profile keys")
		return
	}

	userIDs, employeeIDs := []string{}, []int64{}
	for _, item := range body.Keys {
		switch item.Kind {
		case "userId":
			id, err := uuid.Parse(item.ID)
			if err != nil || id.String() != item.ID {
				problem(w, r, http.StatusBadRequest, "invalid userId")
				return
			}
			userIDs = append(userIDs, item.ID)
		case "employeeId":
			id, err := strconv.ParseInt(item.ID, 10, 64)
			if err != nil || id < 1 || strconv.FormatInt(id, 10) != item.ID {
				problem(w, r, http.StatusBadRequest, "invalid employeeId")
				return
			}
			employeeIDs = append(employeeIDs, id)
		default:
			problem(w, r, http.StatusBadRequest, "invalid key kind")
			return
		}
	}
	found, ok := h.read(w, r, "WHERE user_id = ANY($2::text[]) OR employee_id = ANY($3::bigint[])", userIDs, employeeIDs)
	if !ok {
		return
	}
	index := make(map[key]*profile)
	for i := range found {
		p := &found[i]
		p.WorkEmail = nil
		if p.UserID != nil {
			index[key{"userId", *p.UserID}] = p
		}
		if p.EmployeeID != nil {
			index[key{"employeeId", strconv.FormatInt(*p.EmployeeID, 10)}] = p
		}
	}
	type result struct {
		Key     key      `json:"key"`
		Profile *profile `json:"profile"`
	}
	results := make([]result, 0, len(body.Keys))
	for _, item := range body.Keys {
		results = append(results, result{item, index[item]})
	}
	render.JSON(w, r, map[string][]result{"items": results})
}
