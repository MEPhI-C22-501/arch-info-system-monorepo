package file

import (
	"compress/gzip"
	"fmt"
	"io"
	"os"
)

func compressFile(path string) error {
	source, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open source file: %w", err)
	}
	defer source.Close()

	info, err := source.Stat()
	if err != nil {
		return fmt.Errorf("stat source file: %w", err)
	}

	targetPath := path + ".gz"
	tempPath := targetPath + ".tmp"

	target, err := os.OpenFile(tempPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, info.Mode())
	if err != nil {
		return fmt.Errorf("create compressed file: %w", err)
	}

	gz := gzip.NewWriter(target)
	if _, err := io.Copy(gz, source); err != nil {
		_ = gz.Close()
		_ = target.Close()
		_ = os.Remove(tempPath)

		return fmt.Errorf("compress file: %w", err)
	}

	if err := gz.Close(); err != nil {
		_ = target.Close()
		_ = os.Remove(tempPath)

		return fmt.Errorf("close gzip writer: %w", err)
	}

	if err := target.Close(); err != nil {
		_ = os.Remove(tempPath)

		return fmt.Errorf("close compressed file: %w", err)
	}

	if err := os.Rename(tempPath, targetPath); err != nil {
		_ = os.Remove(tempPath)

		return fmt.Errorf("rename compressed file: %w", err)
	}

	if err := os.Chtimes(targetPath, info.ModTime(), info.ModTime()); err != nil {
		return fmt.Errorf("preserve compressed file time: %w", err)
	}

	if err := os.Remove(path); err != nil {
		return fmt.Errorf("remove source file: %w", err)
	}

	return nil
}
