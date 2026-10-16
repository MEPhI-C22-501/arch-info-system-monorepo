package currencyhndl

import (
	"fmt"
	"io"

	"github.com/xuri/excelize/v2"

	currencydmn "github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/currency"
)

const (
	excelContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	exportFileName   = "currencies.xlsx"
	exportSheetName  = "Currencies"
	exportTimeFormat = "yyyy-mm-dd hh:mm:ss"
)

var exportHeader = []any{
	"Code", "Number", "Name", "Decimals", "Revision", "Last changer", "Created at", "Updated at",
}

// writeCurrenciesExcel writes the currencies as an Excel workbook with a single sheet, one currency per row.
func writeCurrenciesExcel(w io.Writer, currencies []*currencydmn.ExpandedCurrency) error {
	f := excelize.NewFile()
	defer f.Close()

	if err := f.SetSheetName(f.GetSheetName(0), exportSheetName); err != nil {
		return fmt.Errorf("rename sheet: %w", err)
	}

	headerStyle, err := f.NewStyle(&excelize.Style{Font: &excelize.Font{Bold: true}})
	if err != nil {
		return fmt.Errorf("create header style: %w", err)
	}

	timeStyle, err := f.NewStyle(&excelize.Style{CustomNumFmt: new(exportTimeFormat)})
	if err != nil {
		return fmt.Errorf("create time style: %w", err)
	}

	if err := f.SetSheetRow(exportSheetName, "A1", &exportHeader); err != nil {
		return fmt.Errorf("write header: %w", err)
	}

	if err := f.SetRowStyle(exportSheetName, 1, 1, headerStyle); err != nil {
		return fmt.Errorf("set header style: %w", err)
	}

	for i, c := range currencies {
		row := i + 2

		cell, err := excelize.CoordinatesToCellName(1, row)
		if err != nil {
			return fmt.Errorf("currency %d cell: %w", c.ID, err)
		}

		// The number is written as a string to keep its leading zeros.
		values := []any{
			c.Code, c.Number, c.Name, c.Decimals, c.Revision, c.LastChanger.String(), c.CreatedAt, c.UpdatedAt,
		}
		if err := f.SetSheetRow(exportSheetName, cell, &values); err != nil {
			return fmt.Errorf("write currency %d: %w", c.ID, err)
		}
	}

	if len(currencies) > 0 {
		// Created at and updated at are the last two columns.
		from, _ := excelize.CoordinatesToCellName(len(exportHeader)-1, 2)
		to, _ := excelize.CoordinatesToCellName(len(exportHeader), len(currencies)+1)

		if err := f.SetCellStyle(exportSheetName, from, to, timeStyle); err != nil {
			return fmt.Errorf("set time style: %w", err)
		}
	}

	if err := f.SetPanes(exportSheetName, &excelize.Panes{
		Freeze:      true,
		YSplit:      1,
		TopLeftCell: "A2",
		ActivePane:  "bottomLeft",
	}); err != nil {
		return fmt.Errorf("freeze header: %w", err)
	}

	if err := f.SetColWidth(exportSheetName, "A", "H", 20); err != nil {
		return fmt.Errorf("set column width: %w", err)
	}

	if err := f.SetColWidth(exportSheetName, "F", "F", 40); err != nil {
		return fmt.Errorf("set column width: %w", err)
	}

	if _, err := f.WriteTo(w); err != nil {
		return fmt.Errorf("write workbook: %w", err)
	}

	return nil
}
