package pipeline

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
)

var (
	// vttTag matches inline markup: <c>, </c>, and per-word <00:00:01.000> tags.
	vttTag = regexp.MustCompile(`<[^>]*>`)
	// vttCue matches a cue timing line, e.g. "00:00:01.000 --> 00:00:04.000".
	vttCue = regexp.MustCompile(`(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}\.\d{3}|\d{1,2}:\d{2}\.\d{3})`)
)

// ParseVTT parses a WebVTT subtitle file into transcript segments. It is built
// for YouTube auto-captions, stripping inline <timing> tags and dropping the
// rolling duplicate cues those files are full of.
func ParseVTT(path string) ([]TranscriptSegment, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("vtt: open: %w", err)
	}
	defer f.Close()

	var (
		segments  []TranscriptSegment
		cur       *TranscriptSegment
		textLines []string
	)

	flush := func() {
		if cur == nil {
			return
		}
		text := cleanVTTText(strings.Join(textLines, " "))
		// Skip empty cues and the rolling-caption duplicates YouTube emits
		// (a cue whose text repeats, or is a prefix of, the previous one).
		if text != "" {
			if n := len(segments); n == 0 || !overlapsText(segments[n-1].Text, text) {
				cur.Text = text
				segments = append(segments, *cur)
			}
		}
		cur, textLines = nil, nil
	}

	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 1<<20)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if m := vttCue.FindStringSubmatch(line); m != nil {
			flush()
			cur = &TranscriptSegment{Start: parseVTTTime(m[1]), End: parseVTTTime(m[2])}
			continue
		}
		if line == "" {
			flush()
			continue
		}
		if cur != nil {
			textLines = append(textLines, line)
		}
	}
	flush()
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("vtt: scan: %w", err)
	}
	return segments, nil
}

// cleanVTTText strips markup, decodes a few entities, and collapses the
// consecutive duplicate words rolling captions produce.
func cleanVTTText(s string) string {
	s = vttTag.ReplaceAllString(s, "")
	s = strings.NewReplacer("&nbsp;", " ", "&amp;", "&", "&lt;", "<", "&gt;", ">").Replace(s)

	words := strings.Fields(s)
	deduped := words[:0]
	for i, w := range words {
		if i > 0 && deduped[len(deduped)-1] == w {
			continue
		}
		deduped = append(deduped, w)
	}
	return strings.Join(deduped, " ")
}

// overlapsText reports whether next is redundant given prev: identical text,
// or wholly contained in prev (a shrinking rolling-caption frame). A cue that
// adds new words is kept, so no transcript content is lost.
func overlapsText(prev, next string) bool {
	return prev == next || strings.Contains(prev, next)
}

// parseVTTTime converts an "HH:MM:SS.mmm" or "MM:SS.mmm" timestamp to seconds.
func parseVTTTime(s string) float64 {
	parts := strings.Split(s, ":")
	var hours, minutes float64
	var secText string
	switch len(parts) {
	case 3:
		hours, _ = strconv.ParseFloat(parts[0], 64)
		minutes, _ = strconv.ParseFloat(parts[1], 64)
		secText = parts[2]
	case 2:
		minutes, _ = strconv.ParseFloat(parts[0], 64)
		secText = parts[1]
	default:
		return 0
	}
	seconds, _ := strconv.ParseFloat(secText, 64)
	return hours*3600 + minutes*60 + seconds
}
