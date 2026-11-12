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
from Apps.legal.models import LegalDocument
from Apps.progress.models import Badge
from Apps.subscriptions.models import SubscriptionPlan
from Apps.support.models import FAQ

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

FAQS = [
    (
        1,
        "What is EQi30?",
        "EQi30 is a mobile app that helps professionals and leaders build emotional intelligence through 30 trainable abilities — with structured daily 5-minute micro-skill practices.",
    ),
    (
        2,
        "Who is EQi30 for?",
        "It's built for working professionals, team leaders, and organizational leaders who want to develop real emotional and leadership skills through consistent daily practice.",
    ),
    (
        3,
        "How much time do I need each day?",
        "As little as 5 minutes. You choose your own pace — 1, 2, or 3 abilities per day depending on your commitment level.",
    ),
    (
        4,
        "How do I track my progress?",
        "Your progress is tracked automatically through daily practice completion, 5-of-7 weekly streaks, and ability check-ins. Check the Home and Journey tabs to track your growth over time.",
    ),
    (
        5,
        "Can I change my growth pace or subscription plan?",
        "Yes! Go to Profile → Goal to change your daily pace (1, 2, or 3 abilities/day), or Profile → Manage Subscription to view available plans.",
    ),
    (
        6,
        "How do I reset my password?",
        "Go to Profile → Security → Change Password. You'll need to enter your current password and then create a new one.",
    ),
    (
        7,
        "Can I delete my account?",
        "Yes. Go to Profile → Security → Delete Account. Please note that this action is permanent and all your data will be removed within 30 days.",
    ),
    (
        8,
        "How do I contact support?",
        "You can reach us at support@eqi30.com or use the Contact Support option below. We typically respond within 1-2 business days.",
    ),
]

PRIVACY_POLICY_CONTENT = """1. Information We Collect
- Account info — Name, email address, and encrypted credentials.
- Assessment Responses — Your EQ competency ratings and reassessment results.
- Practice Data — Abilities you choose, exercises submitted, and daily reflections.
- Usage & Device Info — App activity, streak consistency, and diagnostics for support.

2. How We Use Your Information
- To create and manage your account.
- To personalize your 30-ability journey and recommended starting priorities.
- To deliver practice reminders at your preferred time.
- To improve coaching guidance, features, and reliability.

3. Sharing & AI Privacy
- We do not sell your personal data to any third party.
- AI coaching conversations are strictly grounded in non-identifying emotional skill development and are never used as clinical medical advice.
- Trusted hosting and notification infrastructure providers may process encrypted data only to operate the app.

4. Data Storage and Security
- Your data is stored on secure, encrypted cloud servers using HTTPS/TLS in transit.
- If you delete your account, all personal data is permanently removed within 30 days.

5. Your Rights & Contact
- Access, correct, export, or delete your account anytime from Profile → Settings.
- Contact privacy@eqi30.com or visit www.eqi30.com."""

TERMS_OF_SERVICE_CONTENT = """1. Acceptance of Terms
By installing or using EQi30, you agree to be bound by these Terms of Service.

2. Eligibility & Account
You must be 18 years or older to use EQi30. You are responsible for keeping your login credentials confidential and notifying support@eqi30.com of unauthorized access.

3. Acceptable Use & Intellectual Property
You agree not to reverse engineer, disrupt, or misuse the service. All EQi30 curriculum, exercises, and design assets remain the intellectual property of EQi30.

4. Health & Professional Disclaimer
EQi30 is a self-development and leadership skill-building tool. It is not a substitute for professional mental health treatment, therapy, or medical advice. If you are experiencing a crisis, please seek licensed professional help.

5. Termination & Contact
You may delete your account anytime via Profile → Security → Delete Account. Questions: privacy@eqi30.com."""


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

        for order, question, answer in FAQS:
            FAQ.objects.update_or_create(
                question=question,
                defaults={
                    "answer": answer,
                    "display_order": order,
                    "is_active": True,
                },
            )

        LegalDocument.objects.update_or_create(
            type=LegalDocument.DocumentType.PRIVACY_POLICY,
            version="1.0",
            defaults={
                "title": "EQi30 Privacy Policy",
                "content": PRIVACY_POLICY_CONTENT,
                "is_active": True,
            },
        )
        LegalDocument.objects.update_or_create(
            type=LegalDocument.DocumentType.TERMS_OF_SERVICE,
            version="1.0",
            defaults={
                "title": "EQi30 Terms of Service",
                "content": TERMS_OF_SERVICE_CONTENT,
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
