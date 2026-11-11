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

# Seed official Doc 2 ability overviews across all 30 abilities
ABILITY_DEFAULTS = {
    # --- Self-Management ---
    "Emotional Awareness": {
        "what_it_is": "Recognizing and naming what you feel in the moment.",
        "why_it_matters": "Improves self-control, reduces reactivity, and clarifies decisions.",
        "what_you_will_do": "Short daily check-ins using simple prompts and a feelings list.",
        "what_you_will_learn": [
            "Name specific emotions instead of just 'fine'",
            "Notice emotions in your body",
            "Understand feelings vs thoughts",
            "Pause and respond vs react",
        ],
    },
    "Boundary Awareness": {
        "what_it_is": "Understanding your personal limits and where you end and others begin.",
        "why_it_matters": "Prevents burnout and ensures your time is spent on your priorities.",
        "what_you_will_do": '"Energy leak" audits and practice saying \'no\' to low-value requests.',
        "what_you_will_learn": [
            "Spot where emotional or time leaks happen",
            "Separate your responsibility from others' reactions",
            "Say 'no' clearly without lingering guilt",
            "Protect high-priority focus blocks",
        ],
    },
    "Self-Confidence": {
        "what_it_is": "Believing in your capacity to handle challenges.",
        "why_it_matters": "Increases willingness to take risks and bounce back from failure.",
        "what_you_will_do": 'An "Evidence Log" to track small wins and strengths daily.',
        "what_you_will_learn": [
            "Track real evidence of capability daily",
            "Calm the inner critic before tough tasks",
            "Take healthy action despite self-doubt",
            "Recover constructively after setbacks",
        ],
    },
    "Self-Actualization": {
        "what_it_is": "The continuous pursuit of personal growth and potential.",
        "why_it_matters": 'Creates a sense of fulfillment and prevents "stagnation" or boredom.',
        "what_you_will_do": 'Weekly "Growth Sprints" focused on one new skill or habit.',
        "what_you_will_learn": [
            "Clarify meaningful personal growth targets",
            "Design 5-minute weekly growth sprints",
            "Align daily choices with core aspirations",
            "Sustain curiosity past initial motivation",
        ],
    },
    "Independence": {
        "what_it_is": "Being self-directed and free from emotional dependency.",
        "why_it_matters": "Builds trust in your own judgment and reduces the need for constant validation.",
        "what_you_will_do": 'Decision-journaling and "solo-choice" exercises.',
        "what_you_will_learn": [
            "Notice reassurance-seeking urges early",
            "Journal independent decisions with conviction",
            "Act from internal values over approval",
            "Own outcomes without second-guessing",
        ],
    },
    # --- Interpersonal Management ---
    "Empathy": {
        "what_it_is": "Sensing and understanding the emotions of others.",
        "why_it_matters": "Builds deep trust, improves teamwork, and reduces social friction.",
        "what_you_will_do": '"Perspective-taking" drills and active listening challenges.',
        "what_you_will_learn": [
            "Listen to understand before replying",
            "Attune to another person's unspoken state",
            "Validate feelings without absorbing them",
            "Reduce relational friction under stress",
        ],
    },
    "Verbal Expression": {
        "what_it_is": "Clearly communicating your thoughts and feelings.",
        "why_it_matters": "Reduces misunderstandings and ensures your message is heard.",
        "what_you_will_do": '"Voice-note" practice and clarity-checks for your daily speech.',
        "what_you_will_learn": [
            "Translate vague feelings into clear words",
            "Deliver honest feedback without blame",
            "Check listener understanding quickly",
            "Keep key messages concise under pressure",
        ],
    },
    "Non-verbal Communication": {
        "what_it_is": "Using body language and tone to reinforce your message.",
        "why_it_matters": "90% of communication is non-verbal; it builds instant rapport.",
        "what_you_will_do": 'Video-selfies and "Mirroring" exercises to align body and voice.',
        "what_you_will_learn": [
            "Align tone, posture, and words",
            "Read tension cues in rooms faster",
            "Use grounded pacing when speaking",
            "Build trust through open presence",
        ],
    },
    "Assertiveness": {
        "what_it_is": "Standing up for your rights without being aggressive.",
        "why_it_matters": "Gains respect from others and ensures your needs are met fairly.",
        "what_you_will_do": '"Script-building" for difficult conversations and boundary setting.',
        "what_you_will_learn": [
            "Express needs directly without apology",
            "Replace passive or sharp pushback",
            "Hold firm boundaries with calm respect",
            "Handle pushback without backing down",
        ],
    },
    "Conflict Management": {
        "what_it_is": "Navigating disagreements toward a positive resolution.",
        "why_it_matters": "Prevents broken relationships and turns tension into innovation.",
        "what_you_will_do": 'Role-play scenarios and "De-escalation" phrase training.',
        "what_you_will_learn": [
            "De-escalate heated exchanges calmly",
            "Separate people from the core problem",
            "Surface shared interests in disagreement",
            "Close conversations with clear next steps",
        ],
    },
    # --- Stress Management ---
    "Stress Tolerance": {
        "what_it_is": "Remaining calm and functional during difficult times.",
        "why_it_matters": 'Prevents "freezing" or panic when things go wrong.',
        "what_you_will_do": "Micro-stress exposures and controlled breathing techniques.",
        "what_you_will_learn": [
            "Stay steady when plans unravel",
            "Use rapid breathing resets under load",
            "Prevent overwhelm from blocking action",
            "Widen your calm window day by day",
        ],
    },
    "Cognitive Flexibility": {
        "what_it_is": "Adjusting your emotions and thoughts to change.",
        "why_it_matters": "Allows you to pivot quickly when your original plan fails.",
        "what_you_will_do": '"The Pivot" exercises—re-framing sudden changes as opportunities.',
        "what_you_will_learn": [
            "Spot rigid 'all-or-nothing' thinking",
            "Generate Plan B options rapidly",
            "Reframe unexpected disruptions calmly",
            "Release attachment to outdated plans",
        ],
    },
    "Emotional Regulation": {
        "what_it_is": "Managing the intensity of your emotional responses.",
        "why_it_matters": 'Keeps you in the "driver’s seat" rather than being driven by moods.',
        "what_you_will_do": '"Cool-down" protocols and emotional labeling under pressure.',
        "what_you_will_learn": [
            "Lower emotional heat in under 90 seconds",
            "Pause between trigger and reaction",
            "Label rising agitation accurately",
            "Choose values-aligned responses over impulses",
        ],
    },
    "Social Resources": {
        "what_it_is": "Tapping into your support network for help.",
        "why_it_matters": "You don't have to carry the load alone; it increases resilience.",
        "what_you_will_do": '"Support Mapping" and practicing the art of asking for help.',
        "what_you_will_learn": [
            "Map trusted mentors, peers, and friends",
            "Ask for specific help without guilt",
            "Notice isolating stress patterns early",
            "Strengthen reciprocal support habits",
        ],
    },
    "Optimism": {
        "what_it_is": 'Finding the "bright side" even in setbacks.',
        "why_it_matters": "Fuels persistence and keeps morale high for yourself and others.",
        "what_you_will_do": '"Three Good Things" logs and identifying the "Seed of Benefit."',
        "what_you_will_learn": [
            "Balance realism with constructive hope",
            "Extract lessons from daily friction",
            "Shift explanatory style after setbacks",
            "Maintain steadier morale across teams",
        ],
    },
    # --- Spirit/Energy Management ---
    "Belief Influence": {
        "what_it_is": "Using your core values to guide your behavior.",
        "why_it_matters": "Provides an internal compass that keeps you consistent.",
        "what_you_will_do": '"Value-sorting" cards and daily alignment checks.',
        "what_you_will_learn": [
            "Name your top 3 non-negotiable values",
            "Check tough choices against your compass",
            "Notice when unspoken rules drive stress",
            "Live with tighter word-to-action integrity",
        ],
    },
    "Clarity": {
        "what_it_is": "Having a crystal-clear vision of your goals.",
        "why_it_matters": 'Eliminates "busy work" and focuses your energy on what counts.',
        "what_you_will_do": '"Vision-casting" prompts and "Noise-reduction" exercises.',
        "what_you_will_learn": [
            "Cut through daily urgency noise",
            "Name the one priority that defines success",
            "Eliminate low-value commitments early",
            "Reconnect work to longer-term purpose",
        ],
    },
    "Energy Awareness": {
        "what_it_is": 'Tracking your physical and mental "battery" levels.',
        "why_it_matters": 'Prevents "pushing through" to the point of exhaustion.',
        "what_you_will_do": "Bi-hourly energy check-ins to find your peak performance hours.",
        "what_you_will_learn": [
            "Identify people and tasks that drain vs recharge",
            "Match demanding work to peak energy hours",
            "Spot early fatigue signals before burnout",
            "Build 5-minute renewal micro-breaks",
        ],
    },
    "Community Building": {
        "what_it_is": "Fostering a sense of belonging with others.",
        "why_it_matters": "Increases longevity and creates a safety net of shared success.",
        "what_you_will_do": '"Connection outreach" tasks and collaborative micro-projects.',
        "what_you_will_learn": [
            "Initiate genuine check-ins with others",
            "Create psychological safety in groups",
            "Invest consistently in key relationships",
            "Turn isolated effort into shared momentum",
        ],
    },
    "Meaning Making": {
        "what_it_is": 'Finding the "Why" behind your daily tasks.',
        "why_it_matters": "Turns mundane work into a mission, boosting motivation.",
        "what_you_will_do": '"Purpose-linking" exercises for your most boring tasks.',
        "what_you_will_learn": [
            "Connect routine tasks to personal purpose",
            "Reframe difficult chapters with meaning",
            "Reduce cynicism during demanding weeks",
            "Anchor effort in who you are becoming",
        ],
    },
    # --- Executive Function ---
    "Planning": {
        "what_it_is": "Developing a roadmap for your objectives.",
        "why_it_matters": "Reduces anxiety by turning big goals into small, doable steps.",
        "what_you_will_do": '"Reverse-engineering" your week and daily roadmap sessions.',
        "what_you_will_learn": [
            "Break overwhelming goals into 15-minute steps",
            "Anticipate bottlenecks before they hit",
            "Adjust timelines realistically without panic",
            "End each day with tomorrow's first step",
        ],
    },
    "Prioritizing": {
        "what_it_is": "Sorting tasks by impact rather than urgency.",
        "why_it_matters": 'Ensures you aren\'t just "busy," but actually productive.',
        "what_you_will_do": 'The "Power of 3" rule and Eisenhower Matrix drills.',
        "what_you_will_learn": [
            "Separate high-impact work from urgent noise",
            "Pick 3 daily non-negotiables cleanly",
            "Protect deep work from constant multitasking",
            "Delegate or drop low-leverage tasks",
        ],
    },
    "Motivation": {
        "what_it_is": "Generating the internal drive to get started.",
        "why_it_matters": 'Overcomes procrastination and keeps momentum during "the dip."',
        "what_you_will_do": '"Identity-based" habit triggers and reward-system design.',
        "what_you_will_learn": [
            "Shrink friction to start in under 2 minutes",
            "Use identity cues instead of willpower",
            "Spot emotional resistance behind delay",
            "Celebrate small completions to lock habit loops",
        ],
    },
    "Attention Span": {
        "what_it_is": "Sustaining focus on a single task without distraction.",
        "why_it_matters": "Essential for deep work and high-quality output.",
        "what_you_will_do": '"Pomodoro" sprints and distraction-blocking environmental audits.',
        "what_you_will_learn": [
            "Single-task cleanly for focused sprints",
            "Notice attention drift without self-criticism",
            "Remove top digital triggers fast",
            "Recover deep focus after interruptions",
        ],
    },
    "Organization": {
        "what_it_is": "Structuring your digital and physical space for flow.",
        "why_it_matters": 'Reduces "mental friction" and time lost looking for things.',
        "what_you_will_do": '"5-Minute Clean" rituals and digital file restructuring.',
        "what_you_will_learn": [
            "Cut cognitive clutter in 5-minute resets",
            "Keep capture lists trusted and lightweight",
            "Standardize recurring digital workflows",
            "Review systems weekly to stop buildup",
        ],
    },
    # --- Decision Making ---
    "Processing Speed": {
        "what_it_is": "Rapidly analyzing data to reach a conclusion.",
        "why_it_matters": "Saves time and allows you to capitalize on fast-moving opportunities.",
        "what_you_will_do": '"Rapid-fire" logic puzzles and quick-decision drills.',
        "what_you_will_learn": [
            "Sort critical signal from noisy detail",
            "Decide reversible choices without overthinking",
            "Synthesize options under time pressure",
            "Break analysis-paralysis loops early",
        ],
    },
    "Impulse Control": {
        "what_it_is": "Resisting the urge to act without thinking.",
        "why_it_matters": 'Prevents costly mistakes and "shopper\'s/actor\'s remorse."',
        "what_you_will_do": 'The "Pause-Button" technique and delayed gratification tests.',
        "what_you_will_learn": [
            "Insert a 10-second pause before replying",
            "Wait out acute emotional urges cleanly",
            "Notice body signals before reactive acts",
            "Choose second-order outcomes over instant relief",
        ],
    },
    "Reality Testing": {
        "what_it_is": "Seeing things as they are, not as you fear or wish.",
        "why_it_matters": "Prevents paranoia or over-optimism from clouding judgment.",
        "what_you_will_do": '"Fact vs. Feeling" audits and seeking outside perspectives.',
        "what_you_will_learn": [
            "Separate observable facts from stories",
            "Test anxious assumptions calmly",
            "Invite disconfirming perspectives safely",
            "Ground decisions in objective evidence",
        ],
    },
    "Abstraction": {
        "what_it_is": 'Seeing patterns and "big picture" concepts.',
        "why_it_matters": "Helps you solve complex problems and innovate.",
        "what_you_will_do": 'Mind-mapping and "First Principles" thinking exercises.',
        "what_you_will_learn": [
            "Spot recurring patterns across situations",
            "Transfer winning solutions to new problems",
            "Zoom out from details to core structure",
            "Extract lessons from both wins and errors",
        ],
    },
    "Problem Solving": {
        "what_it_is": "Finding effective, practical solutions to hurdles.",
        "why_it_matters": "Turns obstacles into stepping stones and reduces stress.",
        "what_you_will_do": 'The "5 Whys" method and brainstorming "What If" scenarios.',
        "what_you_will_learn": [
            "Define root causes before jumping to fixes",
            "Generate three workable options calmly",
            "Weigh tradeoffs with balanced judgment",
            "Turn vague worries into concrete tests",
        ],
    },
}

for ability_name, defaults in ABILITY_DEFAULTS.items():
    ab = Ability.objects.filter(name=ability_name).first()
    if ab:
        ab.what_it_is = defaults["what_it_is"]
        ab.why_it_matters = defaults["why_it_matters"]
        ab.what_you_will_do = defaults["what_you_will_do"]
        if not ab.what_you_will_learn:
            ab.what_you_will_learn = defaults["what_you_will_learn"]
        ab.save()
        print(f"Updated journey intro for {ability_name}")

print("Seeding finished successfully.")

