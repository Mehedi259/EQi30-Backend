import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.learning.models import AbilityDayContent

day_content = AbilityDayContent.objects.first()
if day_content:
    day_content.key_concept = 'Key Concept: Granularity. The ability to distinguish between nuanced feelings (e.g., "annoyed" vs "angry") reduces the emotional intensity by up to 50%.'
    day_content.practice_options = ["Calm", "Annoyed", "Hopeful", "Anxious", "Tired", "Overwhelmed", "Curious"]
    day_content.save()
    print("Updated day content!")
else:
    print("No day content found.")
