package app

import (
	"github.com/go-chi/chi/v5"

	absencedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/absence"
	assignmentdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/assignment"
	countrydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/country"
	employeedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/employee"
	gradedmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/grade"
	orgunitdmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/org_unit"
	positiondmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/position"
	projectroledmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/project_role"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
	salarydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/salary"
	recordrepo "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/repositories/postgres/record"
	employeesrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/employee"
	recordsrv "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/services/record"
	httptr "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server"
	absencehndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/absence"
	assignmenthndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/assignment"
	countryhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/country"
	employeehndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/employee"
	gradehndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/grade"
	orgunithndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/org_unit"
	positionhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/position"
	projectrolehndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/project_role"
	salaryhndl "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/transport/http/server/v1/salary"
	absencev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/absence"
	assignmentv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/assignment"
	countryv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/country"
	employeev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/employee"
	gradev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/grade"
	orgunitv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/org_unit"
	positionv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/position"
	projectrolev1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/project_role"
	salaryv1 "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/api/v1/salary"
	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/postgres"
)

// newCatalogService wires the generic repositories and service of one catalog.
func newCatalogService[F any](desc *record.Descriptor[F], txManager *postgres.TxManager, client *postgres.Client) *recordsrv.Service[F] {
	return recordsrv.NewService(
		desc,
		txManager,
		client,
		recordrepo.NewRepository(client, desc),
		recordrepo.NewRevisionRepository(client, desc.Singular, desc.RevisionTable, desc.RevisionColumn),
	)
}

// catalogMounts builds the services of the catalogs besides currencies and returns the mounts of their handlers.
func catalogMounts(txManager *postgres.TxManager, client *postgres.Client) []httptr.Mount {
	countries := newCatalogService(countrydmn.Descriptor, txManager, client)
	projectRoles := newCatalogService(projectroledmn.Descriptor, txManager, client)
	grades := newCatalogService(gradedmn.Descriptor, txManager, client)
	orgUnits := newCatalogService(orgunitdmn.Descriptor, txManager, client)
	positions := newCatalogService(positiondmn.Descriptor, txManager, client)
	assignments := newCatalogService(assignmentdmn.Descriptor, txManager, client)
	salaries := newCatalogService(salarydmn.Descriptor, txManager, client)
	absences := newCatalogService(absencedmn.Descriptor, txManager, client)
	employees := employeesrv.NewService(newCatalogService(employeedmn.Descriptor, txManager, client), txManager, assignments, salaries)

	return []httptr.Mount{
		func(r chi.Router) {
			h := countryhndl.NewHandler(countries)
			countryv1.HandlerWithOptions(h, countryv1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := projectrolehndl.NewHandler(projectRoles)
			projectrolev1.HandlerWithOptions(h, projectrolev1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := gradehndl.NewHandler(grades)
			gradev1.HandlerWithOptions(h, gradev1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := orgunithndl.NewHandler(orgUnits)
			orgunitv1.HandlerWithOptions(h, orgunitv1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := positionhndl.NewHandler(positions)
			positionv1.HandlerWithOptions(h, positionv1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := employeehndl.NewHandler(employees)
			employeev1.HandlerWithOptions(h, employeev1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := assignmenthndl.NewHandler(assignments)
			assignmentv1.HandlerWithOptions(h, assignmentv1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := salaryhndl.NewHandler(salaries)
			salaryv1.HandlerWithOptions(h, salaryv1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
		func(r chi.Router) {
			h := absencehndl.NewHandler(absences)
			absencev1.HandlerWithOptions(h, absencev1.ChiServerOptions{BaseRouter: r, ErrorHandlerFunc: h.HandleParamError})
		},
	}
}
