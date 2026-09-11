package file

import (
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

var filenameTokens = []struct {
	token  string
	format string
	regexp string
}{
	{
		token:  "YYYY",
		format: "2006",
		regexp: `\d{4}`,
	},
	{
		token:  "YY",
		format: "06",
		regexp: `\d{2}`,
	},
	{
		token:  "MM",
		format: "01",
		regexp: `\d{2}`,
	},
	{
		token:  "DD",
		format: "02",
		regexp: `\d{2}`,
	},
	{
		token:  "HH",
		format: "15",
		regexp: `\d{2}`,
	},
	{
		token:  "mm",
		format: "04",
		regexp: `\d{2}`,
	},
	{
		token:  "SS",
		format: "05",
		regexp: `\d{2}`,
	},
}

func renderFilename(pattern string, now time.Time) (string, error) {
	if pattern == "" {
		return "", fmt.Errorf("filename pattern is empty")
	}

	if filepath.Base(pattern) != pattern {
		return "", fmt.Errorf("filename pattern must not contain directories")
	}

	filename := pattern
	for _, token := range filenameTokens {
		filename = strings.ReplaceAll(filename, token.token, now.Format(token.format))
	}

	if filename == "" {
		return "", fmt.Errorf("filename is empty after rendering pattern")
	}

	return filename, nil
}

func compileFilenameMatcher(
	pattern string,
) (*regexp.Regexp, error) {
	if pattern == "" {
		return nil, fmt.Errorf("filename pattern is empty")
	}

	if filepath.Base(pattern) != pattern {
		return nil, fmt.Errorf("filename pattern must not contain directories")
	}

	var builder strings.Builder
	builder.WriteString("^")

	for i := 0; i < len(pattern); {
		matched := false

		for _, token := range filenameTokens {
			if strings.HasPrefix(pattern[i:], token.token) {
				builder.WriteString(token.regexp)

				i += len(token.token)
				matched = true

				break
			}
		}

		if matched {
			continue
		}

		builder.WriteString(regexp.QuoteMeta(string(pattern[i])))

		i++
	}

	builder.WriteString(`(?:\.gz)?$`)

	matcher, err := regexp.Compile(builder.String())
	if err != nil {
		return nil, fmt.Errorf("compile filename matcher: %w", err)
	}

	return matcher, nil
}
