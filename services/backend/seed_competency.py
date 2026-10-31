import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.abilities.models import Ability, Competency

# 1. Update Competency level
comp = Competency.objects.filter(name="Self-Management").first()
if not comp:
    comp = Competency.objects.first()

if comp:
    comp.what_it_is = "Recognizing & naming what you feel in the moment."
    comp.why_it_matters = "Improves self-control, reduces reactivity, clarifies decisions."
    comp.what_you_will_do = "Short daily check-ins using simple prompts & a feelings list."
    comp.what_you_will_learn = [
        "Name specific emotions instead of just 'fine'",
        "Notice emotions in your body",
        "Understand feelings vs thoughts",
        "Pause and respond vs react"
    ]
    comp.save()
    print(f"Updated {comp.name} competency!")

# 2. Seed Ability journey intros
# Emotional Awareness
ea = Ability.objects.filter(name="Emotional Awareness").first()
if ea:
    ea.what_it_is = "Recognizing & naming what you feel in the moment."
    ea.why_it_matters = "Improves self-control, reduces reactivity, clarifies decisions."
    ea.what_you_will_do = "Short daily check-ins using simple prompts & a feelings list."
    ea.what_you_will_learn = [
        "Name specific emotions instead of just 'fine'",
        "Notice emotions in your body",
        "Understand feelings vs thoughts",
        "Pause and respond vs react"
    ]
    ea.save()
    print("Updated Emotional Awareness ability journey intro!")

# Seed default intro for any other ability that doesn't have an intro yet
ABILITY_DEFAULTS = {
    "Boundary Awareness": {
        "what_it_is": "Recognizing your emotional, mental, and physical limits with clarity.",
        "why_it_matters": "Prevents burnout, protects personal values, and builds respectful relationships.",
        "what_you_will_do": "Daily limit check-ins, practice saying no without guilt, and boundary reset prompts.",
        "what_you_will_learn": [
            "Identify when your boundaries are being crossed",
            "Communicate limits clearly and calmly",
            "Separate others' emotions from your own",
            "Set healthy digital and workday boundaries"
        ],
    },
    "Self-Confidence": {
        "what_it_is": "Trusting in your skills, worth, and capacity to handle life challenges.",
        "why_it_matters": "Enables bold decisions, resilience under failure, and healthy assertiveness.",
        "what_you_will_do": "Short strength-spotting exercises, reframing self-doubt, and tracking small wins.",
        "what_you_will_learn": [
            "Shift from inner critic to inner coach",
            "Acknowledge your genuine achievements",
            "Overcome imposter feelings in key moments",
            "Step into challenging situations with composure"
        ],
    },
    "Self-Actualization": {
        "what_it_is": "Pursuing continuous growth and realizing your personal potential.",
        "why_it_matters": "Brings long-term purpose, deep fulfillment, and alignment with core values.",
        "what_you_will_do": "Daily purpose reflections, goal alignment check-ins, and growth tracking.",
        "what_you_will_learn": [
            "Clarify what matters most to your future",
            "Align daily habits with long-term aspirations",
            "Break through plateaus in personal growth",
            "Cultivate sustained passion and curiosity"
        ],
    },
    "Independence": {
        "what_it_is": "Self-directed decision making free from excessive dependence on approval.",
        "why_it_matters": "Fosters personal autonomy, self-reliance, and decisive leadership.",
        "what_you_will_do": "Independent decision prompts, reducing reassurance-seeking, and autonomous goal setting.",
        "what_you_will_learn": [
            "Trust your internal compass when deciding",
            "Reduce reliance on constant validation",
            "Take full ownership of your choices",
            "Act decisively even amidst uncertainty"
        ],
    },
}

for ability_name, defaults in ABILITY_DEFAULTS.items():
    ab = Ability.objects.filter(name=ability_name).first()
    if ab and not ab.what_it_is:
        ab.what_it_is = defaults["what_it_is"]
        ab.why_it_matters = defaults["why_it_matters"]
        ab.what_you_will_do = defaults["what_you_will_do"]
        ab.what_you_will_learn = defaults["what_you_will_learn"]
        ab.save()
        print(f"Seeded default journey intro for {ability_name}")

print("Seeding finished successfully.")

