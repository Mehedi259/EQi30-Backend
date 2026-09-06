"""Idempotent seed of EQi30 reference data.

Creates/updates the 6 competencies with their 30 abilities, growth plans,
practice time options, subscription plans and badges. Safe to run repeatedly.
Use --demo-content to also generate placeholder day-1 learning content
(real content is managed through Django Admin).
"""

from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from Apps.abilities.models import Ability, Competency
from Apps.journey.models import GrowthPlan, PracticeTimeOption
from Apps.learning.models import AbilityDayContent
from Apps.progress.models import Badge
from Apps.subscriptions.models import SubscriptionPlan

COMPETENCIES = [
    ("SELF_MANAGEMENT", "Self-Management", [
        "Emotional Awareness",
        "Boundary Awareness",
        "Self-Confidence",
        "Self-Actualization",
        "Independence",
    ]),
    ("INTERPERSONAL_MANAGEMENT", "Interpersonal Management", [
        "Empathy",
        "Verbal Expression",
        "Non-verbal Communication",
        "Assertiveness",
        "Conflict Management",
    ]),
    ("STRESS_MANAGEMENT", "Stress Management", [
        "Stress Tolerance",
        "Cognitive Flexibility",
        "Emotional Regulation",
        "Optimism",
        "Social Resources",
    ]),
    ("SPIRIT_MANAGEMENT", "Spirit Management", [
        "Belief Influence",
        "Clarity",
        "Energy Awareness",
        "Community Building",
        "Meaning Making",
    ]),
    ("EXECUTIVE_FUNCTION", "Executive Function", [
        "Planning",
        "Prioritizing",
        "Motivation",
        "Attention Span",
        "Organization",
    ]),
    ("DECISION_MAKING", "Decision Making", [
        "Processing Speed",
        "Impulse Control",
        "Reality Testing",
        "Abstraction",
        "Problem Solving",
    ]),
]

GROWTH_PLANS = [
    ("LOW", "Low", 1, 5),
    ("MEDIUM", "Medium", 2, 10),
    ("HIGH", "High", 3, 15),
]

PRACTICE_TIMES = [
    ("MORNING", "Morning", time(6, 0), time(9, 0), True),
    ("MIDDAY", "Midday", time(11, 0), time(14, 0), True),
    ("EVENING", "Evening", time(19, 0), time(22, 0), True),
    ("FLEXIBLE", "Flexible", None, None, False),
]

SUBSCRIPTION_PLANS = [
    ("BASIC", "Basic", 0, ["Access to the 30-day challenge", "Daily learning content"]),
    ("PRO", "Pro", 9.99, ["Everything in Basic", "Full resources library", "Progress insights"]),
    ("PREMIUM", "Premium", 19.99, ["Everything in Pro", "Meditation & yoga (coming soon)", "Priority support"]),
]

BADGES = [
    ("First Step", "Complete your first session.", Badge.ConditionType.FIRST_SESSION, 1),
    ("On Fire", "Reach a 7-day streak.", Badge.ConditionType.STREAK_DAYS, 7),
    ("Deep Diver", "Complete 10 abilities.", Badge.ConditionType.ABILITIES_COMPLETED, 10),
    ("30 Days", "Complete a full 30-day journey.", Badge.ConditionType.JOURNEY_COMPLETED, 1),
]


class Command(BaseCommand):
    help = "Seed EQi30 reference data (competencies, abilities, plans, badges)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo-content",
            action="store_true",
            help="Also create placeholder day-1 learning content per ability.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        for order, (code, name, abilities) in enumerate(COMPETENCIES, start=1):
            competency, _ = Competency.objects.update_or_create(
                code=code, defaults={"name": name, "display_order": order, "is_active": True}
            )
            for ability_order, ability_name in enumerate(abilities, start=1):
                Ability.objects.update_or_create(
                    competency=competency,
                    name=ability_name,
                    defaults={"default_order": ability_order, "is_active": True},
                )

        for code, name, per_day, minutes in GROWTH_PLANS:
            GrowthPlan.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "abilities_per_day": per_day,
                    "estimated_minutes": minutes,
                    "is_active": True,
                },
            )

        for code, name, start, end, fixed in PRACTICE_TIMES:
            PracticeTimeOption.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "start_time": start,
                    "end_time": end,
                    "is_fixed": fixed,
                },
            )

        for code, name, price, features in SUBSCRIPTION_PLANS:
            SubscriptionPlan.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "price": price,
                    "features": features,
                    "billing_period": SubscriptionPlan.BillingPeriod.MONTHLY,
                    "is_active": True,
                },
            )

        for name, description, condition_type, value in BADGES:
            Badge.objects.update_or_create(
                name=name,
                defaults={
                    "description": description,
                    "condition_type": condition_type,
                    "condition_value": value,
                    "is_active": True,
                },
            )

        if options["demo_content"]:
            for ability in Ability.objects.all():
                AbilityDayContent.objects.get_or_create(
                    ability=ability,
                    day_number=1,
                    defaults={
                        "title": f"Introduction to {ability.name}",
                        "teaching_content": f"[Placeholder] What {ability.name} is and why it matters.",
                        "practice_content": f"[Placeholder] A short in-app practice for {ability.name}.",
                        "real_life_plan": f"[Placeholder] Apply {ability.name} once in real life today.",
                        "reflection_question": f"How did practicing {ability.name} feel today?",
                        "estimated_minutes": 5,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: {Competency.objects.count()} competencies, "
            f"{Ability.objects.count()} abilities, "
            f"{GrowthPlan.objects.count()} growth plans, "
            f"{PracticeTimeOption.objects.count()} practice times, "
            f"{SubscriptionPlan.objects.count()} subscription plans, "
            f"{Badge.objects.count()} badges."
        ))
