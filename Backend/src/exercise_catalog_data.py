"""
Standard exercise catalog: data only, no database code.

Copy to Backend/src/exercise_catalog_data.py. `seed_exercise_catalog()` in
database.py reads CATALOG and inserts anything missing (matched by lower-cased
name), so adding an exercise later means adding one line here.

Conventions
-----------
- category:  "strength" | "cardio" | "flexibility"
- met:       approximate Compendium-of-Physical-Activities style values; tune freely
- equipment: one or more of EQUIPMENT joined by "|" (any-of). "bodyweight" means
             no gym equipment is needed.
- level:     "beginner" | "intermediate" | "advanced"
- muscles:   (muscle_group, role, movement_pattern); strength items need at least one
             "primary". Cardio and flexibility items have no muscles by design.
"""

MUSCLE_GROUPS = (
    "chest", "back", "shoulders", "biceps", "triceps", "forearms",
    "quadriceps", "hamstrings", "glutes", "calves", "abs_core",
)
EQUIPMENT = ("bodyweight", "barbell", "dumbbell", "machines", "cables", "bands", "kettlebell")
LEVELS = ("beginner", "intermediate", "advanced")

P, S = "primary", "secondary"
HPUSH, VPUSH, HPULL, VPULL = "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull"
SQUAT, HINGE, LUNGE, ISO, CORE, CARRY = "squat", "hinge", "lunge", "isolation", "core", "carry"


def _e(name, category, met, equipment, level, description, *muscles):
    return {
        "name": name, "category": category, "met": met, "equipment": equipment,
        "level": level, "description": description, "muscles": list(muscles),
    }


CATALOG = [
    # ── Cardio (no muscle mappings by design) ─────────────────────────
    _e("Running", "cardio", 9.8, "bodyweight", "beginner", "Outdoor or treadmill running"),
    _e("Jogging", "cardio", 7.0, "bodyweight", "beginner", "Easy-pace jogging"),
    _e("Cycling", "cardio", 7.5, "bodyweight", "beginner", "Road, stationary, or mountain biking"),
    _e("Stationary Bike", "cardio", 6.8, "machines", "beginner", "Indoor exercise bike at moderate effort"),
    _e("Swimming", "cardio", 7.0, "bodyweight", "beginner", "Freestyle, breaststroke, laps"),
    _e("Walking", "cardio", 3.8, "bodyweight", "beginner", "Brisk walking or incline treadmill"),
    _e("Hiking", "cardio", 6.0, "bodyweight", "beginner", "Hill or trail walking"),
    _e("Jump Rope", "cardio", 11.0, "bodyweight", "intermediate", "High-intensity rope jumping"),
    _e("HIIT", "cardio", 8.0, "bodyweight", "intermediate", "High-Intensity Interval Training"),
    _e("Rowing Machine", "cardio", 7.0, "machines", "beginner", "Indoor rowing workout"),
    _e("Elliptical", "cardio", 6.5, "machines", "beginner", "Elliptical cross trainer"),
    _e("Stair Climber", "cardio", 8.8, "machines", "intermediate", "Stair-climbing machine"),
    _e("Dancing", "cardio", 5.0, "bodyweight", "beginner", "Dance class or freestyle dancing"),
    _e("Football", "cardio", 7.0, "bodyweight", "beginner", "Casual football (soccer) match or practice"),
    _e("Basketball", "cardio", 6.5, "bodyweight", "beginner", "Pickup or practice basketball"),
    _e("Boxing", "cardio", 7.0, "bodyweight", "intermediate", "Bag work or pad work"),
    _e("Burpees", "cardio", 8.0, "bodyweight", "intermediate", "Full-body conditioning"),
    _e("Jumping Jacks", "cardio", 7.7, "bodyweight", "beginner", "Basic calisthenic conditioning"),
    _e("Mountain Climbers", "cardio", 8.0, "bodyweight", "beginner", "Fast alternating knee drives from plank"),

    # ── Flexibility ───────────────────────────────────────────────────
    _e("Yoga", "flexibility", 2.8, "bodyweight", "beginner", "Hatha, Vinyasa, or restorative yoga"),
    _e("Pilates", "flexibility", 3.0, "bodyweight", "beginner", "Mat or reformer pilates"),
    _e("Stretching", "flexibility", 2.5, "bodyweight", "beginner", "Full-body mobility and flexibility routine"),
    _e("Foam Rolling", "flexibility", 2.0, "bodyweight", "beginner", "Self-myofascial release"),

    # ── Strength: chest ───────────────────────────────────────────────
    _e("Bench Press", "strength", 5.0, "barbell", "intermediate", "Barbell flat bench press for chest",
       ("chest", P, HPUSH), ("triceps", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Incline Bench Press", "strength", 5.0, "barbell", "intermediate", "Barbell press on an incline bench",
       ("chest", P, HPUSH), ("shoulders", S, HPUSH), ("triceps", S, HPUSH)),
    _e("Dumbbell Bench Press", "strength", 4.5, "dumbbell", "beginner", "Flat bench press with dumbbells",
       ("chest", P, HPUSH), ("triceps", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Incline Dumbbell Press", "strength", 4.5, "dumbbell", "intermediate", "Incline bench press with dumbbells",
       ("chest", P, HPUSH), ("shoulders", S, HPUSH), ("triceps", S, HPUSH)),
    _e("Machine Chest Press", "strength", 4.0, "machines", "beginner", "Seated chest press machine",
       ("chest", P, HPUSH), ("triceps", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Dumbbell Fly", "strength", 3.5, "dumbbell", "intermediate", "Chest fly with dumbbells",
       ("chest", P, ISO)),
    _e("Cable Fly", "strength", 3.5, "cables", "intermediate", "Chest fly on a cable stack",
       ("chest", P, ISO)),
    _e("Push-ups", "strength", 4.5, "bodyweight", "beginner", "Bodyweight push-ups",
       ("chest", P, HPUSH), ("triceps", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Knee Push-ups", "strength", 3.8, "bodyweight", "beginner", "Easier push-up variation from the knees",
       ("chest", P, HPUSH), ("triceps", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Dips", "strength", 4.5, "bodyweight", "intermediate", "Parallel bar dips for triceps and chest",
       ("triceps", P, VPUSH), ("chest", S, VPUSH), ("shoulders", S, VPUSH)),

    # ── Strength: back ────────────────────────────────────────────────
    _e("Barbell Row", "strength", 5.0, "barbell", "intermediate", "Bent-over barbell rows for upper back",
       ("back", P, HPULL), ("biceps", S, HPULL)),
    _e("Pull-ups", "strength", 5.0, "bodyweight", "intermediate", "Bodyweight or weighted pull-ups",
       ("back", P, VPULL), ("biceps", S, VPULL)),
    _e("Chin-ups", "strength", 5.0, "bodyweight", "intermediate", "Underhand-grip pull-ups",
       ("back", P, VPULL), ("biceps", S, VPULL)),
    _e("Lat Pulldown", "strength", 4.0, "machines|cables", "beginner", "Seated pulldown to the upper chest",
       ("back", P, VPULL), ("biceps", S, VPULL)),
    _e("Seated Cable Row", "strength", 4.0, "cables", "beginner", "Seated row on a cable station",
       ("back", P, HPULL), ("biceps", S, HPULL)),
    _e("One-Arm Dumbbell Row", "strength", 4.5, "dumbbell", "beginner", "Single-arm row braced on a bench",
       ("back", P, HPULL), ("biceps", S, HPULL)),
    _e("Inverted Row", "strength", 4.5, "bodyweight", "beginner", "Bodyweight row under a bar or sturdy table",
       ("back", P, HPULL), ("biceps", S, HPULL)),
    _e("Face Pull", "strength", 3.5, "cables|bands", "intermediate", "Rear-delt and upper-back pull to the face",
       ("shoulders", P, HPULL), ("back", S, HPULL)),
    _e("Resistance Band Row", "strength", 3.5, "bands", "beginner", "Seated or standing row with a band",
       ("back", P, HPULL), ("biceps", S, HPULL)),
    _e("Back Extension", "strength", 3.8, "bodyweight", "beginner", "Lower-back extensions on a bench or floor",
       ("back", P, HINGE), ("glutes", S, HINGE), ("hamstrings", S, HINGE)),
    _e("Deadlift", "strength", 5.5, "barbell", "advanced", "Conventional or sumo barbell deadlifts",
       ("hamstrings", P, HINGE), ("glutes", P, HINGE), ("back", S, HINGE), ("forearms", S, HINGE)),

    # ── Strength: shoulders ───────────────────────────────────────────
    _e("Overhead Press", "strength", 5.0, "barbell", "intermediate", "Standing or seated barbell shoulder press",
       ("shoulders", P, VPUSH), ("triceps", S, VPUSH)),
    _e("Dumbbell Shoulder Press", "strength", 4.5, "dumbbell", "beginner", "Seated or standing dumbbell press",
       ("shoulders", P, VPUSH), ("triceps", S, VPUSH)),
    _e("Lateral Raise", "strength", 3.5, "dumbbell", "beginner", "Side raises for the lateral delts",
       ("shoulders", P, ISO)),
    _e("Rear Delt Fly", "strength", 3.5, "dumbbell", "intermediate", "Bent-over fly for the rear delts",
       ("shoulders", P, ISO), ("back", S, ISO)),
    _e("Pike Push-ups", "strength", 4.5, "bodyweight", "intermediate", "Hips-high push-ups that load the shoulders",
       ("shoulders", P, VPUSH), ("triceps", S, VPUSH)),
    _e("Band Pull-Apart", "strength", 3.0, "bands", "beginner", "Band pull-aparts for rear delts and upper back",
       ("shoulders", P, HPULL), ("back", S, HPULL)),

    # ── Strength: arms ────────────────────────────────────────────────
    _e("Dumbbell Curl", "strength", 4.5, "dumbbell", "beginner", "Bicep curls with dumbbells",
       ("biceps", P, ISO), ("forearms", S, ISO)),
    _e("Barbell Curl", "strength", 4.5, "barbell", "beginner", "Standing barbell curls",
       ("biceps", P, ISO), ("forearms", S, ISO)),
    _e("Hammer Curl", "strength", 4.5, "dumbbell", "beginner", "Neutral-grip dumbbell curls",
       ("biceps", P, ISO), ("forearms", S, ISO)),
    _e("Resistance Band Curl", "strength", 3.5, "bands", "beginner", "Bicep curls with a band",
       ("biceps", P, ISO)),
    _e("Tricep Pushdown", "strength", 4.0, "cables", "beginner", "Cable pushdowns for triceps",
       ("triceps", P, ISO)),
    _e("Overhead Tricep Extension", "strength", 4.0, "dumbbell", "beginner", "Two-hand overhead dumbbell extension",
       ("triceps", P, ISO)),
    _e("Skull Crushers", "strength", 4.0, "barbell", "intermediate", "Lying barbell triceps extensions",
       ("triceps", P, ISO)),
    _e("Close-Grip Push-ups", "strength", 4.5, "bodyweight", "beginner", "Narrow-hand push-ups for triceps",
       ("triceps", P, HPUSH), ("chest", S, HPUSH), ("shoulders", S, HPUSH)),
    _e("Bench Dips", "strength", 4.0, "bodyweight", "beginner", "Triceps dips with hands on a bench",
       ("triceps", P, VPUSH), ("chest", S, VPUSH), ("shoulders", S, VPUSH)),
    _e("Wrist Curl", "strength", 3.0, "dumbbell", "beginner", "Forearm flexion with a dumbbell",
       ("forearms", P, ISO)),
    _e("Farmer's Carry", "strength", 4.5, "dumbbell", "intermediate", "Walk while holding heavy dumbbells",
       ("forearms", P, CARRY), ("abs_core", S, CARRY), ("shoulders", S, CARRY)),
    _e("Dead Hang", "strength", 3.0, "bodyweight", "beginner", "Hang from a bar for time",
       ("forearms", P, ISO), ("back", S, VPULL)),

    # ── Strength: legs ────────────────────────────────────────────────
    _e("Barbell Squat", "strength", 5.0, "barbell", "intermediate", "Back or front barbell squats for legs",
       ("quadriceps", P, SQUAT), ("glutes", P, SQUAT), ("hamstrings", S, SQUAT)),
    _e("Front Squat", "strength", 5.0, "barbell", "advanced", "Barbell squat held on the front shoulders",
       ("quadriceps", P, SQUAT), ("glutes", S, SQUAT), ("abs_core", S, SQUAT)),
    _e("Goblet Squat", "strength", 4.5, "dumbbell|kettlebell", "beginner", "Squat holding one weight at the chest",
       ("quadriceps", P, SQUAT), ("glutes", P, SQUAT), ("abs_core", S, SQUAT)),
    _e("Bodyweight Squat", "strength", 4.0, "bodyweight", "beginner", "Air squats",
       ("quadriceps", P, SQUAT), ("glutes", P, SQUAT)),
    _e("Leg Press", "strength", 5.0, "machines", "beginner", "Machine leg press",
       ("quadriceps", P, SQUAT), ("glutes", S, SQUAT)),
    _e("Leg Extension", "strength", 3.5, "machines", "beginner", "Seated quad extension machine",
       ("quadriceps", P, ISO)),
    _e("Lunges", "strength", 4.5, "bodyweight", "beginner", "Bodyweight forward or reverse lunges",
       ("quadriceps", P, LUNGE), ("glutes", P, LUNGE), ("hamstrings", S, LUNGE)),
    _e("Dumbbell Lunges", "strength", 5.0, "dumbbell", "intermediate", "Lunges holding dumbbells",
       ("quadriceps", P, LUNGE), ("glutes", P, LUNGE), ("hamstrings", S, LUNGE)),
    _e("Bulgarian Split Squat", "strength", 5.0, "dumbbell|bodyweight", "intermediate", "Rear-foot-elevated split squat",
       ("quadriceps", P, LUNGE), ("glutes", P, LUNGE), ("hamstrings", S, LUNGE)),
    _e("Step-ups", "strength", 4.5, "bodyweight", "beginner", "Step onto a box or bench",
       ("quadriceps", P, LUNGE), ("glutes", P, LUNGE)),
    _e("Romanian Deadlift", "strength", 5.0, "barbell", "intermediate", "Hip-hinge deadlift variation for the hamstrings",
       ("hamstrings", P, HINGE), ("glutes", P, HINGE), ("back", S, HINGE), ("forearms", S, HINGE)),
    _e("Dumbbell Romanian Deadlift", "strength", 4.5, "dumbbell", "beginner", "Hip hinge holding dumbbells",
       ("hamstrings", P, HINGE), ("glutes", P, HINGE), ("back", S, HINGE)),
    _e("Leg Curl", "strength", 3.5, "machines", "beginner", "Seated or lying hamstring curl machine",
       ("hamstrings", P, ISO)),
    _e("Glute Bridge", "strength", 3.5, "bodyweight", "beginner", "Hip raises from the floor",
       ("glutes", P, HINGE), ("hamstrings", S, HINGE)),
    _e("Hip Thrust", "strength", 4.5, "barbell", "intermediate", "Barbell hip thrust for the glutes",
       ("glutes", P, HINGE), ("hamstrings", S, HINGE)),
    _e("Kettlebell Swing", "strength", 8.0, "kettlebell", "intermediate", "Explosive hip hinge with a kettlebell",
       ("glutes", P, HINGE), ("hamstrings", P, HINGE), ("back", S, HINGE), ("abs_core", S, HINGE)),
    _e("Standing Calf Raise", "strength", 3.5, "bodyweight", "beginner", "Calf raises on the floor or a step",
       ("calves", P, ISO)),
    _e("Seated Calf Raise", "strength", 3.0, "machines", "beginner", "Seated calf raise machine",
       ("calves", P, ISO)),

    # ── Strength: core ────────────────────────────────────────────────
    _e("Plank", "strength", 3.5, "bodyweight", "beginner", "Isometric core plank",
       ("abs_core", P, CORE)),
    _e("Side Plank", "strength", 3.5, "bodyweight", "beginner", "Isometric side plank",
       ("abs_core", P, CORE)),
    _e("Crunches", "strength", 3.8, "bodyweight", "beginner", "Floor crunches",
       ("abs_core", P, CORE)),
    _e("Hanging Leg Raise", "strength", 4.0, "bodyweight", "intermediate", "Leg raises hanging from a bar",
       ("abs_core", P, CORE), ("forearms", S, CORE)),
    _e("Russian Twist", "strength", 3.8, "bodyweight", "beginner", "Seated rotational core work",
       ("abs_core", P, CORE)),
    _e("Dead Bug", "strength", 3.0, "bodyweight", "beginner", "Slow alternating limb extensions on your back",
       ("abs_core", P, CORE)),
    _e("Cable Crunch", "strength", 4.0, "cables", "intermediate", "Kneeling cable crunch",
       ("abs_core", P, CORE)),
]
