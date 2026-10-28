package recordhndl

import (
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/xuri/excelize/v2"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/internal/domains/record"
)

const (
	excelContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	exportTimeFormat = "yyyy-mm-dd hh:mm:ss"
	exportDateFormat = "yyyy-mm-dd"
)

// lifecycleHeader follows the columns of the catalog in every export, the same as in the currency export.
var lifecycleHeader = []any{"Revision", "Last changer", "Created at", "Updated at"}

// writeExcel writes the records as an Excel workbook with a single sheet, one record per row.
func writeExcel[F any](w io.Writer, desc *record.Descriptor[F], records []*record.Expanded[F]) error {
	f := excelize.NewFile()
	defer f.Close()

	sheet := sheetName(desc.Plural)
	if err := f.SetSheetName(f.GetSheetName(0), sheet); err != nil {
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

	dateStyle, err := f.NewStyle(&excelize.Style{CustomNumFmt: new(exportDateFormat)})
	if err != nil {
		return fmt.Errorf("create date style: %w", err)
	}

	header := make([]any, 0, len(desc.Export)+len(lifecycleHeader))
	for _, c := range desc.Export {
		header = append(header, c.Title)
	}
	header = append(header, lifecycleHeader...)

	if err := f.SetSheetRow(sheet, "A1", &header); err != nil {
		return fmt.Errorf("write header: %w", err)
	}

	if err := f.SetRowStyle(sheet, 1, 1, headerStyle); err != nil {
		return fmt.Errorf("set header style: %w", err)
	}

	for i, m := range records {
		row := i + 2

		cell, err := excelize.CoordinatesToCellName(1, row)
		if err != nil {
			return fmt.Errorf("%s %d cell: %w", desc.Singular, m.ID, err)
		}

		values := make([]any, 0, len(header))
		for j, c := range desc.Export {
			value := c.Value(m)
			values = append(values, value)

			// calendar dates get the date format, so Excel shows them without a time
			if t, ok := value.(time.Time); ok && !t.IsZero() {
				dateCell, _ := excelize.CoordinatesToCellName(j+1, row)
				if err := f.SetCellStyle(sheet, dateCell, dateCell, dateStyle); err != nil {
					return fmt.Errorf("set date style: %w", err)
				}
			}
		}
		values = append(values, m.Revision, m.LastChanger.String(), m.CreatedAt, m.UpdatedAt)

		if err := f.SetSheetRow(sheet, cell, &values); err != nil {
			return fmt.Errorf("write %s %d: %w", desc.Singular, m.ID, err)
		}
	}

	if len(records) > 0 {
		// created at and updated at are the last two columns
		from, _ := excelize.CoordinatesToCellName(len(header)-1, 2)
		to, _ := excelize.CoordinatesToCellName(len(header), len(records)+1)

		if err := f.SetCellStyle(sheet, from, to, timeStyle); err != nil {
			return fmt.Errorf("set time style: %w", err)
		}
	}

	if err := f.SetPanes(sheet, &excelize.Panes{
		Freeze:      true,
		YSplit:      1,
		TopLeftCell: "A2",
		ActivePane:  "bottomLeft",
	}); err != nil {
		return fmt.Errorf("freeze header: %w", err)
	}

	last, _ := excelize.ColumnNumberToName(len(header))
	if err := f.SetColWidth(sheet, "A", last, 20); err != nil {
		return fmt.Errorf("set column width: %w", err)
	}

	changer, _ := excelize.ColumnNumberToName(len(header) - 2)
	if err := f.SetColWidth(sheet, changer, changer, 40); err != nil {
		return fmt.Errorf("set column width: %w", err)
	}

	if _, err := f.WriteTo(w); err != nil {
		return fmt.Errorf("write workbook: %w", err)
	}

	return nil
}

// sheetName turns the collection name into a sheet title: "org_units" becomes "Org units".
func sheetName(plural string) string {
	name := strings.ReplaceAll(plural, "_", " ")
	if name == "" {
		return "Sheet1"
	}

	return strings.ToUpper(name[:1]) + name[1:]
}
