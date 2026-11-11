import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from Apps.abilities.models import Ability
from Apps.learning.models import AbilityDayContent

# Folder paths
FOLDERS = [
    "Microskills 1-20 ",
    "MicroSkills 21-30 Executive functioning and Decision making ",
]

# Explicit normalized filename-stem -> canonical Ability name overrides
ABILITY_ALIASES = {
    "asssertiveness": "Assertiveness",
    "self actualization": "Self-Actualization",
    "organizational ability": "Organization",
    "non verbal communication micro skill": "Non-verbal Communication",
    "non verbal communication": "Non-verbal Communication",
    "self confidence": "Self-Confidence",
    "social resources, micro skills": "Social Resources",
    "meaning making 1": "Meaning Making",
    "belief infuence": "Belief Influence",
}

DEFAULT_FEELING_OPTIONS = [
    {"emoji": "😌", "label": "Calm"},
    {"emoji": "😠", "label": "Annoyed"},
    {"emoji": "🌱", "label": "Hopeful"},
    {"emoji": "😰", "label": "Anxious"},
    {"emoji": "😴", "label": "Tired"},
    {"emoji": "🌀", "label": "Overwhelmed"},
    {"emoji": "🧐", "label": "Curious"},
]

DASH = r"[\-\–—\u2011]"
TEACH_HDR = r"Teaching\s*:?"
PRAC_HDR = r"(?:Prompt(?:\s*/\s*(?:Practice|In-app practice))?|Practice)\s*:?"
PLAN_HDR = rf"If\s*{DASH}\s*Then\s*:?"
BTN_HDR = r"(?:Button\s*:?|\nPhase\s+\d+:)"


def extract_text_from_docx(filepath):
    """Extract paragraph text from a .docx file across macOS and Linux."""
    try:
        with zipfile.ZipFile(filepath) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = [
            "".join(node.text or "" for node in p.findall(".//w:t", ns))
            for p in root.findall(".//w:p", ns)
        ]
        return "\n".join(paragraphs)
    except Exception:
        try:
            result = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", filepath],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error extracting {filepath}: {e}")
            return ""


def parse_days(text):
    """Parse Day 1..N content blocks into structured AbilityDayContent dicts."""
    pattern = r"(?im)^Day\s+(\d+)\s*[\-\–—:\s]+(.*?)(?=\nDay\s+\d+\s*[\-\–—:\s]|\Z)"
    blocks = re.findall(pattern, text, re.DOTALL)

    parsed_days = []
    for day_num_str, content_block in blocks:
        day_num = int(day_num_str)

        title_match = re.search(
            rf"(?im)^Title\s*:?\s*([^\n]+)",
            content_block,
        )
        teaching_match = re.search(
            rf"{TEACH_HDR}\s*(.*?)(?={PRAC_HDR}|{PLAN_HDR}|\Z)",
            content_block,
            re.DOTALL | re.IGNORECASE,
        )
        practice_match = re.search(
            rf"{PRAC_HDR}\s*(.*?)(?={PLAN_HDR}|{BTN_HDR}|\Z)",
            content_block,
            re.DOTALL | re.IGNORECASE,
        )
        ifthen_match = re.search(
            rf"{PLAN_HDR}\s*(.*?)(?={BTN_HDR}|\Z)",
            content_block,
            re.DOTALL | re.IGNORECASE,
        )

        if title_match and title_match.group(1).strip():
            title = title_match.group(1).strip()
        else:
            first_line = content_block.split("\n", 1)[0]
            first_line = re.split(
                rf"\b{TEACH_HDR}", first_line, maxsplit=1, flags=re.IGNORECASE
            )[0]
            title = first_line.strip(" \t:-–—") or f"Day {day_num}"

        teaching = teaching_match.group(1).strip() if teaching_match else ""
        practice = practice_match.group(1).strip() if practice_match else ""
        ifthen = ifthen_match.group(1).strip() if ifthen_match else ""

        parsed_days.append(
            {
                "day_number": day_num,
                "title": title,
                "teaching_content": teaching,
                "practice_content": practice,
                "real_life_plan": ifthen,
                "reflection_question": "How did today's practice make you feel?",
            }
        )

    return parsed_days


def _normalize_filename(filename):
    """Strip numeric prefixes, program boilerplate, punctuation, and extra spaces."""
    name = re.sub(r"\.docx$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"^\d+\s*", "", name)
    name = re.sub(
        r"Microskill[s]?|Micro-Skill|70[-\s]*Day|60[-\s]*Day|Program|Journey|\(App-Ready\)|2 types|Extra",
        " ",
        name,
        flags=re.IGNORECASE,
    )
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip(" .,:;")
    return name


def find_ability(filename):
    """Match a microskill .docx filename deterministically to its canonical Ability."""
    clean_name = _normalize_filename(filename)
    lowered = clean_name.lower()

    if lowered in ABILITY_ALIASES:
        canonical = ABILITY_ALIASES[lowered]
        matched = Ability.objects.filter(name__iexact=canonical).first()
        if matched:
            return matched

    abilities = list(Ability.objects.all())
    for ability in abilities:
        ab_norm = ability.name.lower().replace("-", " ")
        if ab_norm == lowered or ab_norm in lowered or lowered in ab_norm:
            return ability

    words = lowered.split()
    if words:
        for ability in abilities:
            ab_norm = ability.name.lower().replace("-", " ")
            if words[0] in ab_norm:
                return ability

    return None


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    total_days_seeded = 0

    for folder in FOLDERS:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            print(f"Folder not found: {folder_path}")
            continue

        for filename in sorted(os.listdir(folder_path)):
            if (
                not filename.endswith(".docx")
                or filename.startswith("~")
                or filename.lower().startswith("extra")
            ):
                continue

            filepath = os.path.join(folder_path, filename)
            ability = find_ability(filename)
            if not ability:
                print(f"[!] Could not match file to an Ability: {filename}")
                continue

            print(f"Processing: {filename} -> {ability.name}")
            text = extract_text_from_docx(filepath)
            days = parse_days(text)

            if not days:
                print(f"  -> No days found in {filename}")
                continue

            AbilityDayContent.objects.filter(ability=ability).delete()

            objects_to_create = []
            seen_days = set()
            for day in days:
                if day["day_number"] in seen_days:
                    print(f"    Skipping duplicate Day {day['day_number']}")
                    continue
                seen_days.add(day["day_number"])

                objects_to_create.append(
                    AbilityDayContent(
                        ability=ability,
                        day_number=day["day_number"],
                        title=day["title"][:200],
                        teaching_content=day["teaching_content"],
                        practice_content=day["practice_content"],
                        real_life_plan=day["real_life_plan"],
                        reflection_question=day["reflection_question"],
                        practice_options=DEFAULT_FEELING_OPTIONS,
                        estimated_minutes=5,
                    )
                )

            AbilityDayContent.objects.bulk_create(objects_to_create)
            print(f"  -> Successfully seeded {len(objects_to_create)} days.")
            total_days_seeded += len(objects_to_create)

    # Also update any remaining rows (such as Self-Confidence from .xlsx fixture)
    # that still carry the placeholder outcome tags instead of emotion options.
    placeholder_labels = {"More calm", "More clear", "More focused", "No change yet"}
    updated_extra = 0
    for row in AbilityDayContent.objects.all():
        labels = {
            opt.get("label") for opt in (row.practice_options or []) if isinstance(opt, dict)
        }
        if labels == placeholder_labels:
            row.practice_options = DEFAULT_FEELING_OPTIONS
            row.save(update_fields=["practice_options"])
            updated_extra += 1

    print(
        f"\nDone! Seeded {total_days_seeded} days from .docx; "
        f"updated feelings on {updated_extra} additional rows."
    )


if __name__ == "__main__":
    main()
