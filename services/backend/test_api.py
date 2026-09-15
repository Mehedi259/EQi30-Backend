import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.abilities.models import Ability
from django.urls import resolve

try:
    ability = Ability.objects.get(id=3)
    print(f"Ability found: {ability.name}, Competency: {ability.competency.name}")
except Exception as e:
    print(f"Error finding ability: {e}")

try:
    match = resolve('/api/v1/abilities/3/competency/')
    print(f"Route resolves to: {match.func.__name__}")
except Exception as e:
    print(f"Route resolution failed: {e}")
