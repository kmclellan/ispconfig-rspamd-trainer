from .inventory import SpamSource, access_mode_summary
from .orchestrator import RunInProgress
from .policy import MailboxPolicy
from .protocol import validate_request


class DependencyUnavailable(RuntimeError):
    pass


class TrainerService:
    def __init__(
        self,
        state,
        inventory_source=None,
        rspamd=None,
        coordinator=None,
        dependency_errors=None,
    ):
        self.state = state
        self.inventory_source = inventory_source
        self.rspamd = rspamd
        self.coordinator = coordinator
        self.dependency_errors = dict(dependency_errors or {})

    def _require(self, value, name):
        if value is None:
            raise DependencyUnavailable("{} is not configured".format(name))
        return value

    def _inventory_payload(self):
        records = self.state.list_inventory(present=True)
        return {
            "mailboxes": [
                {
                    "mailbox_id": item.mailbox_id,
                    "email": item.email,
                    "server_id": item.server_id,
                    "imap_enabled": item.imap_enabled,
                    "pop3_enabled": item.pop3_enabled,
                    "active": item.active,
                    "doveadm_enabled": item.doveadm_enabled,
                    "access_mode": item.access_mode,
                }
                for item in records
            ],
            "access_modes": access_mode_summary(records),
        }

    def _refresh_inventory(self):
        source = self._require(self.inventory_source, "ISPConfig mailbox source")
        records = source.list_mailboxes()
        return self.state.reconcile_inventory(records)

    def _run(self, dry_run):
        coordinator = self._require(self.coordinator, "trainer coordinator")
        # Runs fail closed if the configured inventory snapshot cannot be
        # refreshed. This avoids training against stale renamed/deleted users.
        self._refresh_inventory()
        run_id = self.state.start_run(dry_run=dry_run)
        try:
            summary = coordinator.execute(dry_run=dry_run)
            payload = summary.as_dict()
            payload["run_id"] = run_id
            status = "partial" if summary.failed else "success"
            self.state.finish_run(run_id, payload, status=status)
            return payload
        except RunInProgress:
            self.state.finish_run(run_id, {}, status="busy", error_class="RunInProgress")
            raise
        except Exception as exc:
            self.state.finish_run(
                run_id,
                {},
                status="failed",
                error_class=type(exc).__name__,
            )
            raise

    def handle(self, request):
        op, args = validate_request(request)

        if op == "health":
            inventory_available = self.inventory_source is not None
            if inventory_available and hasattr(self.inventory_source, "available"):
                inventory_available = bool(self.inventory_source.available())
            return {
                "ok": True,
                "service": "ispconfig-rspamd-trainer",
                "inventory_source": inventory_available,
                "rspamd": self.rspamd is not None,
                "coordinator": self.coordinator is not None,
                "dependency_errors": dict(self.dependency_errors),
            }

        if op == "status":
            inventory = self._inventory_payload()
            return {
                "inventory_count": len(inventory["mailboxes"]),
                "access_modes": inventory["access_modes"],
                "policy_count": len(self.state.list_policies()),
                "spam_source_count": len(
                    self.state.list_spam_sources(enabled_only=True)
                ),
                "latest_run": self.state.latest_run(),
                "dependencies": {
                    "inventory_source": self.inventory_source is not None,
                    "rspamd": self.rspamd is not None,
                    "coordinator": self.coordinator is not None,
                },
                "dependency_errors": dict(self.dependency_errors),
            }

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

        if op == "inventory_list":
            return self._inventory_payload()

        if op == "spam_source_list":
            return {
                "spam_sources": [
                    source.__dict__ for source in self.state.list_spam_sources()
                ]
            }

        if op == "spam_source_set":
            if not isinstance(args["enabled"], bool):
                raise ValueError("enabled must be boolean")
            source = SpamSource(
                mailbox_id=int(args["mailbox_id"]),
                enabled=args["enabled"],
                archive_mailbox=str(args["archive_mailbox"]),
                ham_mailbox=str(args["ham_mailbox"]),
            ).validate()
            if source.enabled and self.state.get_inventory(source.mailbox_id) is None:
                raise ValueError("cannot enable unknown mailbox as spam source")
            self.state.set_spam_source(source)
            return {"spam_source": source.__dict__}

        if op == "discovery":
            result = self._refresh_inventory()
            result.update(self._inventory_payload())
            return result

        if op == "classifier_stats":
            rspamd = self._require(self.rspamd, "Rspamd controller")
            return {"stats": rspamd.stat()}

        if op == "dry_run":
            return self._run(dry_run=True)

        if op == "run":
            return self._run(dry_run=False)

        raise AssertionError("unreachable")
