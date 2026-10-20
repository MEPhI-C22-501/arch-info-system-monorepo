package record

import "time"

// Cell turns a field value into a spreadsheet cell value: pointers are dereferenced, nil becomes an empty cell.
func Cell(v any) any {
	switch p := v.(type) {
	case *string:
		if p == nil {
			return ""
		}

		return *p
	case *int64:
		if p == nil {
			return ""
		}

		return *p
	case *int32:
		if p == nil {
			return ""
		}

		return *p
	case *float64:
		if p == nil {
			return ""
		}

		return *p
	case *bool:
		if p == nil {
			return ""
		}

		return *p
	case *time.Time:
		if p == nil {
			return ""
		}

		return *p
	default:
		return v
	}
}
