from datetime import date as Date, datetime, timedelta, timezone
from sqlmodel import Session, select

from src.auth.auth import hash_password
from src.models import (
    DailySummary,
    Exercise,
    ExerciseCatalogItem,
    ExerciseMuscleMapping,
    FoodItem,
    FoodPortion,
    Habit,
    HabitLog,
    Meal,
    MealItem,
    User,
    WeightLog,
)
from src.routers.daily_summary import calculate_daily_summary


def seed_admin_and_dummy_data(session: Session) -> User:
    """
    Ensure the default 'admin' user exists and has rich dummy data
    for all use cases (profile, weight logs, foods, meals, exercises,
    habits and habit logs, daily summary).
    """
    today = Date.today()
    utc_now = datetime.now(timezone.utc)

    # 1. Admin User
    admin = session.exec(
        select(User).where(
            User.username == "admin",
            User.deleted_at.is_(None),
        )
    ).first()

    if not admin:
        admin = User(
            username="admin",
            hashed_password=hash_password("admin123"),
            weight=75.0,
            height=180.0,
            birthdate=Date(1995, 5, 15),
            created_at=utc_now - timedelta(days=30),
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)

    # 2. Weight logs
    existing_weight = session.exec(
        select(WeightLog).where(WeightLog.user_id == admin.id)
    ).first()
    if not existing_weight:
        weight_entries = [
            (today - timedelta(days=21), 76.8),
            (today - timedelta(days=14), 76.2),
            (today - timedelta(days=7), 75.6),
            (today, 75.0),
        ]
        for w_date, w_val in weight_entries:
            session.add(
                WeightLog(
                    user_id=admin.id,
                    date=w_date,
                    weight=w_val,
                )
            )
        session.commit()

    # 3. Standard Foods & Portions
    existing_foods = session.exec(select(FoodItem)).first()
    food_map: dict[str, FoodItem] = {}
    portion_map: dict[str, FoodPortion] = {}

    if not existing_foods:
        foods_to_create = [
            FoodItem(
                name="Oatmeal",
                calories_per_100g=389.0,
                protein_per_100g=16.9,
                carbs_per_100g=66.3,
                fat_per_100g=6.9,
                base_unit="g",
            ),
            FoodItem(
                name="Banana",
                calories_per_100g=89.0,
                protein_per_100g=1.1,
                carbs_per_100g=22.8,
                fat_per_100g=0.3,
                base_unit="g",
            ),
            FoodItem(
                name="Chicken Breast",
                calories_per_100g=165.0,
                protein_per_100g=31.0,
                carbs_per_100g=0.0,
                fat_per_100g=3.6,
                base_unit="g",
            ),
            FoodItem(
                name="Brown Rice",
                calories_per_100g=111.0,
                protein_per_100g=2.6,
                carbs_per_100g=23.0,
                fat_per_100g=0.9,
                base_unit="g",
            ),
            FoodItem(
                name="Greek Yogurt",
                calories_per_100g=59.0,
                protein_per_100g=10.0,
                carbs_per_100g=3.6,
                fat_per_100g=0.4,
                base_unit="g",
            ),
            FoodItem(
                name="Salmon Fillet",
                calories_per_100g=208.0,
                protein_per_100g=20.4,
                carbs_per_100g=0.0,
                fat_per_100g=13.4,
                base_unit="g",
            ),
            FoodItem(
                name="Boiled Egg",
                calories_per_100g=155.0,
                protein_per_100g=12.6,
                carbs_per_100g=1.1,
                fat_per_100g=10.6,
                base_unit="g",
            ),
        ]
        session.add_all(foods_to_create)
        session.commit()
        for f in foods_to_create:
            session.refresh(f)
            food_map[f.name] = f

        # Create portions
        portions_to_create = [
            FoodPortion(food_id=food_map["Oatmeal"].id, name="1 cup cooked", quantity=1.0, unit="cup", gram_weight=234.0),
            FoodPortion(food_id=food_map["Oatmeal"].id, name="1 bowl", quantity=1.0, unit="bowl", gram_weight=150.0),
            FoodPortion(food_id=food_map["Banana"].id, name="1 medium banana", quantity=1.0, unit="banana", gram_weight=118.0),
            FoodPortion(food_id=food_map["Chicken Breast"].id, name="1 breast fillet", quantity=1.0, unit="fillet", gram_weight=172.0),
            FoodPortion(food_id=food_map["Brown Rice"].id, name="1 cup cooked", quantity=1.0, unit="cup", gram_weight=195.0),
            FoodPortion(food_id=food_map["Greek Yogurt"].id, name="1 cup", quantity=1.0, unit="cup", gram_weight=245.0),
            FoodPortion(food_id=food_map["Salmon Fillet"].id, name="1 fillet", quantity=1.0, unit="fillet", gram_weight=180.0),
            FoodPortion(food_id=food_map["Boiled Egg"].id, name="1 large egg", quantity=1.0, unit="egg", gram_weight=50.0),
        ]
        session.add_all(portions_to_create)
        session.commit()
        for p in portions_to_create:
            session.refresh(p)
            portion_map[f"{p.food_id}_{p.name}"] = p
    else:
        all_foods = session.exec(select(FoodItem).where(FoodItem.deleted_at.is_(None))).all()
        for f in all_foods:
            food_map[f.name] = f
        all_portions = session.exec(select(FoodPortion)).all()
        for p in all_portions:
            portion_map[f"{p.food_id}_{p.name}"] = p

    # 4. Meals & Meal Items
    existing_meals = session.exec(
        select(Meal).where(Meal.user_id == admin.id, Meal.deleted_at.is_(None))
    ).first()

    if not existing_meals and "Oatmeal" in food_map and "Chicken Breast" in food_map:
        # Today Breakfast
        oatmeal = food_map["Oatmeal"]
        banana = food_map["Banana"]
        oat_portion = portion_map.get(f"{oatmeal.id}_1 bowl")
        ban_portion = portion_map.get(f"{banana.id}_1 medium banana")

        oat_grams = oat_portion.gram_weight if oat_portion else 150.0
        ban_grams = ban_portion.gram_weight if ban_portion else 118.0

        oat_cal = round((oatmeal.calories_per_100g / 100.0) * oat_grams, 1)
        oat_p = round((oatmeal.protein_per_100g / 100.0) * oat_grams, 1)
        oat_c = round((oatmeal.carbs_per_100g / 100.0) * oat_grams, 1)
        oat_f = round((oatmeal.fat_per_100g / 100.0) * oat_grams, 1)

        ban_cal = round((banana.calories_per_100g / 100.0) * ban_grams, 1)
        ban_p = round((banana.protein_per_100g / 100.0) * ban_grams, 1)
        ban_c = round((banana.carbs_per_100g / 100.0) * ban_grams, 1)
        ban_f = round((banana.fat_per_100g / 100.0) * ban_grams, 1)

        m1 = Meal(
            user_id=admin.id,
            date=today,
            calories=oat_cal + ban_cal,
            protein=oat_p + ban_p,
            carbs=oat_c + ban_c,
            fat=oat_f + ban_f,
        )
        session.add(m1)
        session.commit()
        session.refresh(m1)

        session.add(
            MealItem(
                meal_id=m1.id,
                food_id=oatmeal.id,
                portion_id=oat_portion.id if oat_portion else None,
                quantity=1.0,
                unit="bowl",
                gram_weight=oat_grams,
                calories=oat_cal,
                protein=oat_p,
                carbs=oat_c,
                fat=oat_f,
            )
        )
        session.add(
            MealItem(
                meal_id=m1.id,
                food_id=banana.id,
                portion_id=ban_portion.id if ban_portion else None,
                quantity=1.0,
                unit="banana",
                gram_weight=ban_grams,
                calories=ban_cal,
                protein=ban_p,
                carbs=ban_c,
                fat=ban_f,
            )
        )

        # Today Lunch
        chicken = food_map["Chicken Breast"]
        rice = food_map["Brown Rice"]
        chk_portion = portion_map.get(f"{chicken.id}_1 breast fillet")
        rice_portion = portion_map.get(f"{rice.id}_1 cup cooked")

        chk_grams = chk_portion.gram_weight if chk_portion else 172.0
        rice_grams = rice_portion.gram_weight if rice_portion else 195.0

        chk_cal = round((chicken.calories_per_100g / 100.0) * chk_grams, 1)
        chk_p = round((chicken.protein_per_100g / 100.0) * chk_grams, 1)
        chk_c = round((chicken.carbs_per_100g / 100.0) * chk_grams, 1)
        chk_f = round((chicken.fat_per_100g / 100.0) * chk_grams, 1)

        rice_cal = round((rice.calories_per_100g / 100.0) * rice_grams, 1)
        rice_p = round((rice.protein_per_100g / 100.0) * rice_grams, 1)
        rice_c = round((rice.carbs_per_100g / 100.0) * rice_grams, 1)
        rice_f = round((rice.fat_per_100g / 100.0) * rice_grams, 1)

        m2 = Meal(
            user_id=admin.id,
            date=today,
            calories=chk_cal + rice_cal,
            protein=chk_p + rice_p,
            carbs=chk_c + rice_c,
            fat=chk_f + rice_f,
        )
        session.add(m2)
        session.commit()
        session.refresh(m2)

        session.add(
            MealItem(
                meal_id=m2.id,
                food_id=chicken.id,
                portion_id=chk_portion.id if chk_portion else None,
                quantity=1.0,
                unit="fillet",
                gram_weight=chk_grams,
                calories=chk_cal,
                protein=chk_p,
                carbs=chk_c,
                fat=chk_f,
            )
        )
        session.add(
            MealItem(
                meal_id=m2.id,
                food_id=rice.id,
                portion_id=rice_portion.id if rice_portion else None,
                quantity=1.0,
                unit="cup",
                gram_weight=rice_grams,
                calories=rice_cal,
                protein=rice_p,
                carbs=rice_c,
                fat=rice_f,
            )
        )

        # Yesterday Dinner
        if "Salmon Fillet" in food_map:
            salmon = food_map["Salmon Fillet"]
            sal_portion = portion_map.get(f"{salmon.id}_1 fillet")
            sal_grams = sal_portion.gram_weight if sal_portion else 180.0

            sal_cal = round((salmon.calories_per_100g / 100.0) * sal_grams, 1)
            sal_p = round((salmon.protein_per_100g / 100.0) * sal_grams, 1)
            sal_c = round((salmon.carbs_per_100g / 100.0) * sal_grams, 1)
            sal_f = round((salmon.fat_per_100g / 100.0) * sal_grams, 1)

            m3 = Meal(
                user_id=admin.id,
                date=today - timedelta(days=1),
                calories=sal_cal + rice_cal,
                protein=sal_p + rice_p,
                carbs=sal_c + rice_c,
                fat=sal_f + rice_f,
            )
            session.add(m3)
            session.commit()
            session.refresh(m3)

            session.add(
                MealItem(
                    meal_id=m3.id,
                    food_id=salmon.id,
                    portion_id=sal_portion.id if sal_portion else None,
                    quantity=1.0,
                    unit="fillet",
                    gram_weight=sal_grams,
                    calories=sal_cal,
                    protein=sal_p,
                    carbs=sal_c,
                    fat=sal_f,
                )
            )
            session.add(
                MealItem(
                    meal_id=m3.id,
                    food_id=rice.id,
                    portion_id=rice_portion.id if rice_portion else None,
                    quantity=1.0,
                    unit="cup",
                    gram_weight=rice_grams,
                    calories=rice_cal,
                    protein=rice_p,
                    carbs=rice_c,
                    fat=rice_f,
                )
            )

        session.commit()
        calculate_daily_summary(session, admin.id, today)
        calculate_daily_summary(session, admin.id, today - timedelta(days=1))

    # 5. Exercises
    existing_exercises = session.exec(
        select(Exercise).where(Exercise.user_id == admin.id, Exercise.deleted_at.is_(None))
    ).first()

    if not existing_exercises:
        exercises_to_add = [
            Exercise(
                user_id=admin.id,
                date=today,
                name="Running",
                category="cardio",
                duration_minutes=30,
                distance_km=5.0,
                intensity="moderate",
                calories_burned=294.0,
            ),
            Exercise(
                user_id=admin.id,
                date=today,
                name="Bench Press",
                category="strength",
                sets=4,
                reps=10,
                weight_kg=70.0,
                duration_minutes=35,
                intensity="moderate",
                calories_burned=175.0,
            ),
            Exercise(
                user_id=admin.id,
                date=today - timedelta(days=1),
                name="Barbell Squat",
                category="strength",
                sets=4,
                reps=8,
                weight_kg=90.0,
                duration_minutes=40,
                intensity="high",
                calories_burned=220.0,
            ),
            Exercise(
                user_id=admin.id,
                date=today - timedelta(days=1),
                name="Yoga",
                category="flexibility",
                duration_minutes=25,
                intensity="low",
                calories_burned=75.0,
            ),
        ]
        session.add_all(exercises_to_add)
        session.commit()
        calculate_daily_summary(session, admin.id, today)
        calculate_daily_summary(session, admin.id, today - timedelta(days=1))

    # 6. Habits & Habit Logs
    existing_habits = session.exec(
        select(Habit).where(Habit.user_id == admin.id, Habit.deleted_at.is_(None))
    ).first()

    if not existing_habits:
        habit_created = utc_now - timedelta(days=35)
        h1 = Habit(
            user_id=admin.id,
            name="Drink 2L Water",
            description="Daily hydration goal",
            color="#3B82F6",
            target_per_week=7,
            frequency="daily",
            created_at=habit_created,
        )
        h2 = Habit(
            user_id=admin.id,
            name="Gym Workout",
            description="Resistance and strength training",
            color="#EF4444",
            target_per_week=4,
            frequency="weekly",
            created_at=habit_created,
        )
        h3 = Habit(
            user_id=admin.id,
            name="Read 20 Pages",
            description="Read educational or fiction books",
            color="#10B981",
            target_per_week=5,
            frequency="weekly",
            created_at=habit_created,
        )
        h4 = Habit(
            user_id=admin.id,
            name="10,000 Steps",
            description="Daily walking target",
            color="#F59E0B",
            target_per_week=6,
            frequency="weekly",
            created_at=habit_created,
        )
        session.add_all([h1, h2, h3, h4])
        session.commit()
        session.refresh(h1)
        session.refresh(h2)
        session.refresh(h3)
        session.refresh(h4)

        # Habit logs over the last 14 days and today
        logs = []
        # Habit 1: Drink Water (daily - almost every day)
        for offset in [0, 1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13]:
            logs.append(HabitLog(habit_id=h1.id, user_id=admin.id, date=today - timedelta(days=offset), completed=True))

        # Habit 2: Gym (4x/week)
        for offset in [1, 3, 5, 8, 10, 12]:
            logs.append(HabitLog(habit_id=h2.id, user_id=admin.id, date=today - timedelta(days=offset), completed=True))

        # Habit 3: Read (5x/week)
        for offset in [0, 2, 4, 6, 7, 9, 11]:
            logs.append(HabitLog(habit_id=h3.id, user_id=admin.id, date=today - timedelta(days=offset), completed=True))

        # Habit 4: 10,000 Steps (6x/week)
        for offset in [1, 2, 3, 5, 6, 8, 9, 10, 13]:
            logs.append(HabitLog(habit_id=h4.id, user_id=admin.id, date=today - timedelta(days=offset), completed=True))

        session.add_all(logs)
        session.commit()

    return admin
