#!/usr/bin/env bash
# Leak scan: keeps brand, client and creator names out of anything this repo shares.
#
#   scripts/leak-scan.sh             scan every tracked file, and untracked files git would add
#   scripts/leak-scan.sh --history   also every past version of every file, every commit message, every ref
#
# The patterns are private and never committed: one extended regex per line in .leak-patterns.local
# (git-ignored), and/or newline-separated in the LEAK_PATTERNS environment variable (for CI).
# Exits 1 on any hit, 2 when there are no patterns to scan with.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
PAT=$(mktemp)
trap 'rm -f "$PAT"' EXIT
if [ -f .leak-patterns.local ]; then grep -v -e '^#' -e '^[[:space:]]*$' .leak-patterns.local >> "$PAT"; fi
if [ -n "${LEAK_PATTERNS:-}" ]; then printf '%s\n' "$LEAK_PATTERNS" | grep -v -e '^[[:space:]]*$' >> "$PAT"; fi
if [ ! -s "$PAT" ]; then
  echo "leak-scan: no patterns (.leak-patterns.local or LEAK_PATTERNS) - refusing to call this clean"
  exit 2
fi
echo "leak-scan: $(wc -l < "$PAT" | tr -d ' ') patterns"
hits=0
scan_files() {  # judged by output, not exit code: BSD xargs exits 0 without running grep on an empty list
  local out
  out=$(xargs -0 grep -H -n -i -I -E -f "$PAT" -- 2>/dev/null)
  if [ -n "$out" ]; then echo "$out"; hits=1; fi
  return 0
}
scan_files < <(git ls-files -z)
scan_files < <(git ls-files -z --others --exclude-standard)
if [ "${1:-}" = "--history" ]; then
  for c in $(git rev-list --all); do
    git grep -n -i -I -E -f "$PAT" "$c" -- && hits=1
  done
  git log --all --format='%H %an <%ae>%n%B' | grep -n -i -E -f "$PAT" && hits=1
  git for-each-ref --format='%(refname:short)' | grep -i -E -f "$PAT" && hits=1
fi
if [ "$hits" = 1 ]; then
  echo "leak-scan: FOUND private names above - remove them before sharing"
  exit 1
fi
echo "leak-scan: clean"
