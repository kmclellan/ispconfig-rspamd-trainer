from .policy import MailboxPolicy
from .protocol import validate_request


class TrainerService:
    def __init__(self, state):
        self.state = state

    def handle(self, request):
        op, args = validate_request(request)
        if op == "health":
            return {"ok": True, "service": "ispconfig-rspamd-trainer"}
        if op == "policy_list":
            return {"policies": [p.__dict__ for p in self.state.list_policies()]}
        if op == "policy_get":
            policy = self.state.get_policy(int(args["mailbox_id"]))
            return {"policy": None if policy is None else policy.__dict__}
        if op == "policy_set":
            policy = MailboxPolicy(
                mailbox_id=int(args["mailbox_id"]),
                mode=str(args["mode"]),
                age_days=int(args["age_days"]),
                batch_size=int(args["batch_size"]),
            ).validate()
            self.state.set_policy(policy)
            return {"policy": policy.__dict__}
        if op in {"status", "discovery", "classifier_stats", "dry_run", "run"}:
            return {
                "ok": False,
                "implemented": False,
                "operation": op,
                "message": "reserved protocol operation; target integration pending",
            }
        raise AssertionError("unreachable")
