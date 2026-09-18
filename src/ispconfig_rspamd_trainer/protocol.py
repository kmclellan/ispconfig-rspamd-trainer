ALLOWED_OPERATIONS = {
    "health": frozenset(),
    "status": frozenset(),
    "policy_list": frozenset(),
    "policy_get": frozenset({"mailbox_id"}),
    "policy_set": frozenset({"mailbox_id", "mode", "age_days", "batch_size"}),
    "inventory_list": frozenset(),
    "spam_source_list": frozenset(),
    "spam_source_set": frozenset(
        {"mailbox_id", "enabled", "archive_mailbox", "ham_mailbox"}
    ),
    "discovery": frozenset(),
    "classifier_stats": frozenset(),
    "dry_run": frozenset(),
    "run": frozenset(),
}


def validate_request(request):
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    op = request.get("op")
    if op not in ALLOWED_OPERATIONS:
        raise ValueError("unknown operation")
    args = request.get("args", {})
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    if set(args) != set(ALLOWED_OPERATIONS[op]):
        raise ValueError("unexpected or missing arguments")
    return op, args
