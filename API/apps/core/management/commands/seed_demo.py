"""Seed demo data: python manage.py seed_demo

Creates admin/committee/resident users, wings & flats, services with
flat-service mapping + audit trail, an announcement, a pending payment,
an issue and expenses so every screen has something to show. (Idempotent.)
"""
import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction

from API.apps.accounts.models import User
from API.apps.announcements.models import Announcement
from API.apps.expenses.models import Expense
from API.apps.flats.models import Flat, Service, Wing
from API.apps.flats.services import set_flat_service
from API.apps.issues.models import Issue, IssueComment, IssueVote
from API.apps.payments.services import submit_payment


class Command(BaseCommand):
    help = "Seed the database with demo society data (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        # ---- users -------------------------------------------------------
        admin, created = User.objects.get_or_create(
            username="admin", defaults={"role": "admin", "first_name": "Society", "last_name": "Admin"})
        if created:
            admin.set_password("admin@123"); admin.is_staff = True; admin.save()
        committee, created = User.objects.get_or_create(
            username="committee", defaults={"role": "committee", "first_name": "Committee", "last_name": "Member"})
        if created:
            committee.set_password("committee@123"); committee.save()
        resident, created = User.objects.get_or_create(
            username="resident", defaults={"role": "resident", "first_name": "Ravi", "last_name": "Kumar", "phone": "9876543210"})
        if created:
            resident.set_password("resident@123"); resident.save()
        r2, created = User.objects.get_or_create(
            username="priya", defaults={"role": "resident", "first_name": "Priya", "last_name": "Sharma"})
        if created:
            r2.set_password("resident@123"); r2.save()

        # ---- wings & flats ----------------------------------------------
        wing_a, _ = Wing.objects.get_or_create(name="A", defaults={"description": "North block"})
        wing_b, _ = Wing.objects.get_or_create(name="B", defaults={"description": "South block"})
        flats = []
        for w, prefix in [(wing_a, "A"), (wing_b, "B")]:
            for floor in (1, 2):
                for no in (1, 2):
                    f, _ = Flat.objects.get_or_create(
                        wing=w, flat_no=f"{prefix}-{floor}{no}",
                        defaults={"floor": floor, "area_sqft": 950 + floor * 100,
                                  "owner_name": f"Owner {prefix}{floor}{no}",
                                  "monthly_maintenance": 2500})
                    flats.append(f)
        flats[0].owner = resident; flats[0].owner_name = "Ravi Kumar"; flats[0].save()
        flats[2].owner = r2; flats[2].owner_name = "Priya Sharma"; flats[2].save()

        # ---- services + per-flat enablement (audited) -------------------
        water, _ = Service.objects.get_or_create(name="Water Connection", defaults={"monthly_charges": 300})
        power, _ = Service.objects.get_or_create(name="Electricity Backup", defaults={"monthly_charges": 450})
        parking, _ = Service.objects.get_or_create(name="Parking Slot", defaults={"monthly_charges": 600})
        club, _ = Service.objects.get_or_create(name="Clubhouse Access", defaults={"monthly_charges": 200})
        for svc in (water, power, parking):
            set_flat_service(flats[0], svc, "enable", admin, "Default services on move-in")
        set_flat_service(flats[0], club, "disable", admin, "Renovation in progress")
        set_flat_service(flats[2], water, "enable", admin, "")

        # ---- announcement -------------------------------------------------
        Announcement.objects.get_or_create(
            title="Annual Maintenance Billing Starts",
            defaults={"body": "The maintenance bill for this month is now open. Please pay via the portal "
                              "and upload your UTR receipt for approval. Water supply will be shut from "
                              "10 AM to 1 PM on Sunday for tank cleaning.",
                      "pinned": True, "created_by": admin,
                      "expiry_date": dt.date.today() + dt.timedelta(days=30)})

        # ---- pending payment (demo of approval workflow) ------------------
        if not resident.payments_submitted.exists():
            submit_payment({
                "flat": flats[0], "amount": 2500, "receipt_no": "UTR202609X001",
                "mode": "upi", "remark": "September maintenance",
                "period_month": 9, "period_year": 2026,
            }, resident)

        # ---- issues with votes/comments ------------------------------------
        issue, _ = Issue.objects.get_or_create(
            flat=flats[0], title="Lift B not working since morning",
            defaults={"description": "The lift in Wing A is stuck at floor 2 since 8 AM. Senior citizens "
                                     "are facing difficulty.",
                      "category": "elevator", "priority": "urgent", "status": "in_progress",
                      "created_by": resident})
        IssueComment.objects.get_or_create(issue=issue, user=r2,
                                           defaults={"comment": "Same issue here, very slow response."})
        if not issue.votes.exists():
            IssueVote.objects.create(issue=issue, user=r2)

        # ---- expenses (transparency) ---------------------------------------
        Expense.objects.get_or_create(
            title="Security guard salaries - September", category="salaries", amount=48000,
            paid_to="SafeWatch Security LLP", expense_date=dt.date(2026, 9, 1),
            defaults={"added_by": admin, "description": "3 guards x Rs.16,000"})
        Expense.objects.get_or_create(
            title="Corridor painting - Wing B", category="maintenance", amount=22500,
            paid_to="Shree Contractors", expense_date=dt.date(2026, 9, 10),
            defaults={"added_by": admin})

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded OK\n"
            "  Admin      -> admin / admin@123\n"
            "  Committee  -> committee / committee@123\n"
            "  Resident   -> resident / resident@123  (flat A-101)\n"
            "  Resident2  -> priya / resident@123     (flat A-201)"))
