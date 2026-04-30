#!/bin/bash
# T010: Verify --json outputs valid JSON with dependency fields
SCRIPT="$(dirname "$0")/../../stale-audit.py"
OUTPUT=$(python "$SCRIPT" --json 2>&1)

# Check valid JSON
echo "$OUTPUT" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "FAIL: --json output is not valid JSON"
  exit 1
fi

# Check dependency fields exist
echo "$OUTPUT" | python3 -c "
import sys, json
repos = json.load(sys.stdin)
assert len(repos) > 0, 'No repos found'
r = repos[0]
for field in ['depends_on', 'depended_on_by', 'dep_protected']:
    assert field in r, f'Missing field: {field}'
print(f'PASS: {len(repos)} repos, all have dependency fields')
"
