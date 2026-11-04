package groupopssrv

import (
	"context"

	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
)

// Salaries serves the salaries catalog: the standard methods plus the group change of an org unit.
type Salaries struct {
	*recordsrv.Service[salarydmn.Fields]

	group *Service
}

// Salaries returns the service of the salaries handler.
func (s *Service) Salaries() *Salaries {
	return &Salaries{Service: s.salaries, group: s}
}

func (s *Salaries) Revise(ctx context.Context, request *salarydmn.GroupChangeRequest) (*salarydmn.GroupChangeResult, error) {
	return s.group.ReviseSalaries(ctx, request)
}

// Assignments serves the assignments catalog: the standard methods plus the transfer of an org unit.
type Assignments struct {
	*recordsrv.Service[assignmentdmn.Fields]

	group *Service
}

// Assignments returns the service of the assignments handler.
func (s *Service) Assignments() *Assignments {
	return &Assignments{Service: s.assignments, group: s}
}

func (a *Assignments) Transfer(ctx context.Context, request *assignmentdmn.TransferRequest) (*assignmentdmn.TransferResult, error) {
	return a.group.TransferAssignments(ctx, request)
}
