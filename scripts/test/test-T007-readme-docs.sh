#!/bin/bash
# T007: Verify README documents all CLI flags
README="$(dirname "$0")/../../README.md"
FAILS=0

for flag in "--json" "--archive" "--dry-run" "--summary" "--dir" "--yes" "--deps"; do
  if ! grep -qF -- "$flag" "$README"; then
    echo "FAIL: $flag not documented in README.md"
    FAILS=$((FAILS + 1))
  fi
done

if [ "$FAILS" -eq 0 ]; then
  echo "PASS: All CLI flags documented in README"
else
  echo "$FAILS flags missing"
  exit 1
fi
