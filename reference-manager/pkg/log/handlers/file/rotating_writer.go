package file

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"sync"
	"time"

	"github.com/MEPhI-C22-501/arch-info-system-monorepo/reference-manager/pkg/log/config"
)

type rotatingWriter struct {
	mu sync.Mutex

	location string
	config   config.RotationConfig
	matcher  *regexp.Regexp

	file     *os.File
	path     string
	size     int64
	openedAt time.Time
}

type backup struct {
	path    string
	modTime time.Time
}

func newRotatingWriter(cfg config.FileConfig) (*rotatingWriter, error) {
	if cfg.Rotation.FilenamePattern == "" {
		return nil, fmt.Errorf("filename_pattern is required when rotation is enabled")
	}

	if cfg.Rotation.MaxSize < 0 {
		return nil, fmt.Errorf("max_size must not be negative")
	}

	if cfg.Rotation.MaxAge < 0 {
		return nil, fmt.Errorf("max_age must not be negative")
	}

	if cfg.Rotation.MaxBackups < 0 {
		return nil, fmt.Errorf("max_backups must not be negative")
	}

	matcher, err := compileFilenameMatcher(cfg.Rotation.FilenamePattern)
	if err != nil {
		return nil, fmt.Errorf("compile filename matcher: %w", err)
	}

	writer := &rotatingWriter{
		location: cfg.Location,
		config:   cfg.Rotation,
		matcher:  matcher,
	}

	now := time.Now()

	if err := writer.openNewFile(now); err != nil {
		return nil, err
	}

	if err := writer.cleanup(); err != nil {
		_ = writer.file.Close()
		return nil, err
	}

	return writer, nil
}

func (w *rotatingWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	now := time.Now()

	if w.shouldRotate(int64(len(p)), now) {
		if err := w.rotate(now); err != nil {
			return 0, err
		}
	}

	n, err := w.file.Write(p)
	if err != nil {
		return n, err
	}

	w.size += int64(n)

	return n, nil
}

func (w *rotatingWriter) shouldRotate(incoming int64, now time.Time) bool {
	return w.shouldRotateBySize(incoming) || w.shouldRotateByAge(now)
}

func (w *rotatingWriter) shouldRotateBySize(incoming int64) bool {
	if w.config.MaxSize <= 0 {
		return false
	}

	if w.size == 0 {
		return false
	}

	return w.size+incoming > w.config.MaxSize
}

func (w *rotatingWriter) shouldRotateByAge(now time.Time) bool {
	if w.config.MaxAge <= 0 {
		return false
	}

	return now.Sub(w.openedAt) >= w.config.MaxAge
}

func (w *rotatingWriter) rotate(now time.Time) error {
	oldFile := w.file
	oldPath := w.path

	if err := oldFile.Close(); err != nil {
		return fmt.Errorf("close log file %q: %w", oldPath, err)
	}

	w.file = nil

	if w.config.Compress {
		if err := compressFile(oldPath); err != nil {
			return fmt.Errorf("compress log file %q: %w", oldPath, err)
		}
	}

	if err := w.openNewFile(now); err != nil {
		return err
	}

	if err := w.cleanup(); err != nil {
		return fmt.Errorf("cleanup rotated log files: %w", err)
	}

	return nil
}

func (w *rotatingWriter) openNewFile(now time.Time) error {
	filename, err := renderFilename(w.config.FilenamePattern, now)
	if err != nil {
		return fmt.Errorf("render filename: %w", err)
	}

	path := filepath.Join(w.location, filename)

	if path == w.path {
		return fmt.Errorf(
			"filename pattern generated the same filename %q; increase filename pattern precision",
			filename,
		)
	}

	file, err := os.OpenFile(
		path,
		os.O_CREATE|os.O_APPEND|os.O_WRONLY,
		defaultFileMode,
	)
	if err != nil {
		return fmt.Errorf("open log file %q: %w", path, err)
	}

	info, err := file.Stat()
	if err != nil {
		_ = file.Close()
		return fmt.Errorf("stat log file %q: %w", path, err)
	}

	w.file = file
	w.path = path
	w.size = info.Size()
	w.openedAt = now

	return nil
}

func (w *rotatingWriter) cleanup() error {
	entries, err := os.ReadDir(w.location)
	if err != nil {
		return fmt.Errorf("read log directory %q: %w", w.location, err)
	}

	backups := make([]backup, 0, len(entries))

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		if !w.matcher.MatchString(entry.Name()) {
			continue
		}

		path := filepath.Join(w.location, entry.Name())
		if path == w.path {
			continue
		}

		info, err := entry.Info()
		if err != nil {
			return fmt.Errorf("get log file info %q: %w", path, err)
		}

		backups = append(backups, backup{
			path:    path,
			modTime: info.ModTime(),
		})
	}

	if w.config.MaxBackups <= 0 {
		return nil
	}

	sort.Slice(backups, func(i, j int) bool {
		return backups[i].modTime.After(backups[j].modTime)
	})

	if len(backups) <= w.config.MaxBackups {
		return nil
	}

	for _, backup := range backups[w.config.MaxBackups:] {
		if err := os.Remove(backup.path); err != nil && !os.IsNotExist(err) {
			return fmt.Errorf("remove old backup %q: %w", backup.path, err)
		}
	}

	return nil
}

func (w *rotatingWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.file == nil {
		return nil
	}

	err := w.file.Close()
	w.file = nil

	return err
}
