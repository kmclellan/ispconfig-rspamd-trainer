from pathlib import Path

from .inventory import SpamSource, access_mode_summary
from .orchestrator import RunInProgress
from .policy import MailboxPolicy, aged_inbox_allowed
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
        observer_socket_path=None,
    ):
        self.state = state
        self.inventory_source = inventory_source
        self.rspamd = rspamd
        self.coordinator = coordinator
        self.dependency_errors = dict(dependency_errors or {})
        self.observer_socket_path = observer_socket_path

    def _require(self, value, name):
        if value is None:
            raise DependencyUnavailable("{} is not configured".format(name))
        return value

    def _observer_available(self):
        if not self.observer_socket_path:
            return False
        return Path(self.observer_socket_path).exists()

    def _inventory_payload(self):
        records = self.state.list_inventory(present=True)
        spam_sources = {
            source.mailbox_id: source
            for source in self.state.list_spam_sources(enabled_only=True)
        }
        mailboxes = []
        for item in records:
            configured_policy = self.state.get_policy(item.mailbox_id)
            policy = configured_policy or MailboxPolicy(item.mailbox_id)
            observation = self.state.get_observation(item.mailbox_id)
            if observation.last_imap and observation.last_pop3:
                observed_access = "mixed"
            elif observation.last_pop3:
                observed_access = "pop3"
            elif observation.last_imap:
                observed_access = "imap"
            else:
                observed_access = "unknown"
            mailboxes.append(
                {
                    "mailbox_id": item.mailbox_id,
                    "email": item.email,
                    "server_id": item.server_id,
                    "imap_enabled": item.imap_enabled,
                    "pop3_enabled": item.pop3_enabled,
                    "active": item.active,
                    "doveadm_enabled": item.doveadm_enabled,
                    "access_mode": item.access_mode,
                    "observed_access": observed_access,
                    "observed_since": (
                        None
                        if observation.observed_since is None
                        else observation.observed_since.isoformat()
                    ),
                    "last_imap": (
                        None
                        if observation.last_imap is None
                        else observation.last_imap.isoformat()
                    ),
                    "last_pop3": (
                        None
                        if observation.last_pop3 is None
                        else observation.last_pop3.isoformat()
                    ),
                    "policy": policy.__dict__,
                    "policy_is_default": configured_policy is None,
                    "aged_inbox_eligible": aged_inbox_allowed(
                        policy,
                        observation,
                        imap_enabled=item.imap_enabled,
                        pop3_enabled=item.pop3_enabled,
                    ),
                    "dedicated_spam_source": item.mailbox_id in spam_sources,
                }
            )
        return {
            "mailboxes": mailboxes,
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
                "observer": self._observer_available(),
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
                    "observer": self._observer_available(),
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
