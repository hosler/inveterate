import json
from pathlib import Path

from django.core.management.base import BaseCommand
from proxmoxer.core import ResourceException

from inveterate.models import Cluster
from inveterate.proxmox import get_proxmox_connection


class Command(BaseCommand):
    help = "Sync the 'inveterate' firewall group to all Proxmox clusters from fixtures/firewall_rules.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fixture = Path(__file__).resolve().parent.parent.parent / "fixtures" / "firewall_rules.json"

        if not fixture.exists():
            self.stderr.write(f"Fixture not found: {fixture}")
            return

        data = json.loads(fixture.read_text())
        group_name = data["group"]
        desired_rules = data["rules"]

        clusters = Cluster.objects.all()
        if not clusters.exists():
            self.stdout.write("No clusters configured — nothing to sync.")
            return

        for cluster in clusters:
            self.stdout.write(f"\n--- Cluster: {cluster.name} ({cluster.host}) ---")
            try:
                proxmox = get_proxmox_connection(cluster)

                # Ensure cluster firewall is enabled
                opts = proxmox.cluster.firewall.options.get()
                if not opts.get("enable"):
                    if dry_run:
                        self.stdout.write("  Would enable cluster firewall")
                    else:
                        proxmox.cluster.firewall.options.put(enable=1)
                        self.stdout.write("  Enabled cluster firewall")

                # Create group if missing
                groups = [g["group"] for g in proxmox.cluster.firewall.groups.get()]
                if group_name not in groups:
                    if dry_run:
                        self.stdout.write(f"  Would create group '{group_name}'")
                    else:
                        proxmox.cluster.firewall.groups.post(group=group_name)
                        self.stdout.write(f"  Created group '{group_name}'")

                # Get existing rules
                existing = proxmox.cluster.firewall.groups(group_name).get()

                # Delete existing rules (in reverse order to preserve positions)
                if existing:
                    if dry_run:
                        self.stdout.write(f"  Would delete {len(existing)} existing rules")
                    else:
                        for rule in reversed(existing):
                            proxmox.cluster.firewall.groups(group_name)(rule["pos"]).delete()
                        self.stdout.write(f"  Deleted {len(existing)} existing rules")

                # Create desired rules in order
                for i, rule in enumerate(desired_rules):
                    desc = f"{rule['type']:>3} {rule['action']:<6}"
                    if "source" in rule:
                        desc += f" src={rule['source']}"
                    if "dest" in rule:
                        desc += f" dst={rule['dest']}"
                    if "comment" in rule:
                        desc += f"  # {rule['comment']}"

                    if dry_run:
                        self.stdout.write(f"  [{i}] Would add: {desc}")
                    else:
                        proxmox.cluster.firewall.groups(group_name).post(**rule)
                        self.stdout.write(f"  [{i}] Added: {desc}")

                self.stdout.write(f"  Synced {len(desired_rules)} rules to '{group_name}'")

            except ResourceException as e:
                self.stderr.write(f"  Proxmox API error: {e}")
            except Exception as e:
                self.stderr.write(f"  Error: {e}")
