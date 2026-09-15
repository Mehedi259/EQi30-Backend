import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.abilities.models import Competency

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
else:
    print("No competency found.")
