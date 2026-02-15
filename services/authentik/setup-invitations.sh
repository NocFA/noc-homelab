#!/usr/bin/env bash
# One-time (idempotent): configure Authentik enrollment flow for invite-based user signup.
# Reads AUTHENTIK_BOOTSTRAP_TOKEN from services/authentik/.env
# Usage: ./setup-invitations.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load token from .env
ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found"
    exit 1
fi
AUTHENTIK_BOOTSTRAP_TOKEN=$(grep '^AUTHENTIK_BOOTSTRAP_TOKEN=' "$ENV_FILE" | cut -d= -f2-)
if [[ -z "$AUTHENTIK_BOOTSTRAP_TOKEN" ]]; then
    echo "ERROR: AUTHENTIK_BOOTSTRAP_TOKEN not set in $ENV_FILE"
    exit 1
fi

API="https://auth.nocfa.net/api/v3"
AUTH="Authorization: Bearer $AUTHENTIK_BOOTSTRAP_TOKEN"
CT="Content-Type: application/json"

api_get() {
    curl -sf -H "$AUTH" "$API$1" 2>/dev/null || echo '{}'
}

api_post() {
    curl -sf -X POST -H "$AUTH" -H "$CT" -d "$2" "$API$1" 2>/dev/null || echo '{}'
}

# Helper: check if resource exists by searching results
exists_by_slug() {
    local endpoint="$1" slug="$2"
    local resp
    resp=$(api_get "${endpoint}?slug=${slug}")
    local count
    count=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pagination',{}).get('count',0))" 2>/dev/null || echo 0)
    [[ "$count" -gt 0 ]]
}

exists_by_name() {
    local endpoint="$1" name="$2"
    local resp
    resp=$(api_get "${endpoint}?name=${name}")
    local count
    count=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pagination',{}).get('count',0))" 2>/dev/null || echo 0)
    [[ "$count" -gt 0 ]]
}

get_pk_by_slug() {
    local endpoint="$1" slug="$2"
    local resp
    resp=$(api_get "${endpoint}?slug=${slug}")
    echo "$resp" | python3 -c "import sys,json; r=json.load(sys.stdin).get('results',[]); print(r[0]['pk'] if r else '')" 2>/dev/null
}

get_pk_by_name() {
    local endpoint="$1" name="$2"
    local resp
    resp=$(api_get "${endpoint}?name=${name}")
    echo "$resp" | python3 -c "import sys,json; r=json.load(sys.stdin).get('results',[]); print(r[0]['pk'] if r else '')" 2>/dev/null
}

FLOW_SLUG="enrollment-invitation"

echo "=== Authentik Invitation Enrollment Setup ==="
echo ""

# 1. Create enrollment flow
echo -n "1. Enrollment flow ($FLOW_SLUG)... "
if exists_by_slug "/flows/instances/" "$FLOW_SLUG"; then
    echo "already exists"
else
    resp=$(api_post "/flows/instances/" "{
        \"slug\": \"$FLOW_SLUG\",
        \"name\": \"Enrollment (Invitation)\",
        \"title\": \"Sign up\",
        \"designation\": \"enrollment\"
    }")
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('slug')" 2>/dev/null; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi
FLOW_PK=$(get_pk_by_slug "/flows/instances/" "$FLOW_SLUG")

# 2. Create invitation stage
INVITE_STAGE="invitation-stage"
echo -n "2. Invitation stage ($INVITE_STAGE)... "
if exists_by_name "/stages/invitation/stages/" "$INVITE_STAGE"; then
    echo "already exists"
else
    resp=$(api_post "/stages/invitation/stages/" "{
        \"name\": \"$INVITE_STAGE\",
        \"continue_flow_without_invitation\": false
    }")
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('pk')" 2>/dev/null; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi
INVITE_PK=$(get_pk_by_name "/stages/invitation/stages/" "$INVITE_STAGE")

# 3. Create prompt stage (username, email, name, password, password-repeat)
PROMPT_STAGE="enrollment-prompt"
echo -n "3. Prompt stage ($PROMPT_STAGE)... "
if exists_by_name "/stages/prompt/stages/" "$PROMPT_STAGE"; then
    echo "already exists"
else
    # Get or create required prompt fields
    get_or_create_field() {
        local field_name="$1" label="$2" field_type="$3" order="$4" required="$5"
        local pk
        pk=$(api_get "/stages/prompt/prompts/?field_key=${field_name}" | python3 -c "import sys,json; r=json.load(sys.stdin).get('results',[]); print(r[0]['pk'] if r else '')" 2>/dev/null)
        if [[ -n "$pk" ]]; then
            echo "$pk"
            return
        fi
        local resp
        resp=$(api_post "/stages/prompt/prompts/" "{
            \"field_key\": \"$field_name\",
            \"label\": \"$label\",
            \"type\": \"$field_type\",
            \"required\": $required,
            \"placeholder\": \"$label\",
            \"order\": $order
        }")
        echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pk',''))" 2>/dev/null
    }

    USERNAME_PK=$(get_or_create_field "username" "Username" "username" 0 "true")
    NAME_PK=$(get_or_create_field "name" "Name" "text" 1 "true")
    EMAIL_PK=$(get_or_create_field "email" "Email" "email" 2 "true")
    PASSWORD_PK=$(get_or_create_field "password" "Password" "password" 3 "true")
    PASSWORD_REPEAT_PK=$(get_or_create_field "password_repeat" "Password (repeat)" "password" 4 "true")

    resp=$(api_post "/stages/prompt/stages/" "{
        \"name\": \"$PROMPT_STAGE\",
        \"fields\": [\"$USERNAME_PK\", \"$NAME_PK\", \"$EMAIL_PK\", \"$PASSWORD_PK\", \"$PASSWORD_REPEAT_PK\"],
        \"validation_policies\": []
    }")
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('pk')" 2>/dev/null; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi
PROMPT_PK=$(get_pk_by_name "/stages/prompt/stages/" "$PROMPT_STAGE")

# 3b. Create validation policy for prompt fields
POLICY_NAME="enrollment-username-validation"
echo -n "3b. Validation policy ($POLICY_NAME)... "
POLICY_EXPR='import re

prompt_data = request.context.get("prompt_data", {})
username = prompt_data.get("username", "")
name = prompt_data.get("name", "")
email = prompt_data.get("email", "")

if not username:
    ak_message("Username is required.")
    return False

if not re.match(r"^[a-z0-9._-]+$", username):
    ak_message("Username must contain only lowercase letters, numbers, hyphens, underscores, and dots. No capitals or spaces.")
    return False

if len(username) < 3:
    ak_message("Username must be at least 3 characters.")
    return False

if len(username) > 32:
    ak_message("Username must be 32 characters or fewer.")
    return False

if not name or len(name.strip()) < 1:
    ak_message("Name is required.")
    return False

if len(name) > 64:
    ak_message("Name must be 64 characters or fewer.")
    return False

if not email or "@" not in email:
    ak_message("A valid email address is required.")
    return False

return True'

POLICY_PK=$(api_get "/policies/expression/?name=$POLICY_NAME" | python3 -c "import sys,json; r=json.load(sys.stdin).get('results',[]); print(r[0]['pk'] if r else '')" 2>/dev/null)
if [[ -n "$POLICY_PK" ]]; then
    echo "already exists"
else
    POLICY_JSON=$(python3 -c "import json; print(json.dumps({'name':'$POLICY_NAME','execution_logging':False,'expression':'''$POLICY_EXPR'''}))")
    resp=$(api_post "/policies/expression/" "$POLICY_JSON")
    POLICY_PK=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pk',''))" 2>/dev/null)
    if [[ -n "$POLICY_PK" ]]; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi

# Ensure policy is bound to prompt stage
CURRENT_POLICIES=$(api_get "/stages/prompt/stages/$PROMPT_PK/" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin).get('validation_policies',[])))" 2>/dev/null)
if echo "$CURRENT_POLICIES" | python3 -c "import sys,json; sys.exit(0 if '$POLICY_PK' in json.load(sys.stdin) else 1)" 2>/dev/null; then
    : # already bound
else
    echo -n "   Binding policy to prompt stage... "
    curl -sf -X PATCH -H "$AUTH" -H "$CT" \
        -d "{\"validation_policies\": [\"$POLICY_PK\"]}" \
        "$API/stages/prompt/stages/$PROMPT_PK/" >/dev/null 2>&1
    echo "done"
fi

# 4. Create user-write stage
WRITE_STAGE="enrollment-user-write"
echo -n "4. User-write stage ($WRITE_STAGE)... "
if exists_by_name "/stages/user_write/" "$WRITE_STAGE"; then
    echo "already exists"
else
    resp=$(api_post "/stages/user_write/" "{
        \"name\": \"$WRITE_STAGE\",
        \"create_users_as_inactive\": false,
        \"create_users_group\": null,
        \"user_type\": \"internal\"
    }")
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('pk')" 2>/dev/null; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi
WRITE_PK=$(get_pk_by_name "/stages/user_write/" "$WRITE_STAGE")

# 5. Create user-login stage
LOGIN_STAGE="enrollment-user-login"
echo -n "5. User-login stage ($LOGIN_STAGE)... "
if exists_by_name "/stages/user_login/" "$LOGIN_STAGE"; then
    echo "already exists"
else
    resp=$(api_post "/stages/user_login/" "{
        \"name\": \"$LOGIN_STAGE\",
        \"session_duration\": \"seconds=0\"
    }")
    if echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('pk')" 2>/dev/null; then
        echo "created"
    else
        echo "FAILED: $resp"
        exit 1
    fi
fi
LOGIN_PK=$(get_pk_by_name "/stages/user_login/" "$LOGIN_STAGE")

# 6. Bind stages to flow in order
echo -n "6. Binding stages to flow... "
EXISTING_BINDINGS=$(api_get "/flows/bindings/?target=${FLOW_PK}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pagination',{}).get('count',0))" 2>/dev/null || echo 0)
if [[ "$EXISTING_BINDINGS" -gt 0 ]]; then
    echo "bindings already exist ($EXISTING_BINDINGS found)"
else
    STAGES=("$INVITE_PK" "$PROMPT_PK" "$WRITE_PK" "$LOGIN_PK")
    ORDER=0
    for stage_pk in "${STAGES[@]}"; do
        ORDER=$((ORDER + 10))
        resp=$(api_post "/flows/bindings/" "{
            \"target\": \"$FLOW_PK\",
            \"stage\": \"$stage_pk\",
            \"order\": $ORDER
        }")
        if ! echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('pk')" 2>/dev/null; then
            echo "FAILED binding stage $stage_pk: $resp"
            exit 1
        fi
    done
    echo "created (4 bindings)"
fi

echo ""
echo "=== Setup Complete ==="
echo "Enrollment flow: https://auth.nocfa.net/if/flow/$FLOW_SLUG/"
echo ""
echo "To create an invitation:"
echo "  curl -sf -H 'Authorization: Bearer $AUTHENTIK_BOOTSTRAP_TOKEN' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -X POST '$API/stages/invitation/invitations/' \\"
echo "    -d '{\"name\": \"test-invite\", \"flow\": \"$FLOW_PK\"}'"
