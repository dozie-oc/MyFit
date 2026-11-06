import 'package:flutter_test/flutter_test.dart';
import 'package:myfit_app/models/models.dart';

void main() {
  group('UserGoal Model', () {
    test('fromJson and toJson roundtrip', () {
      final json = {
        'id': 1,
        'goal_type': 'build_muscle',
        'target_weight': 78.5,
        'target_date': '2026-12-31',
        'activity_level': 'moderately_active',
        'training_days_per_week': 4,
        'training_experience': 'intermediate',
        'available_equipment': 'barbell, dumbbell, machines',
        'dietary_preference': 'omnivore',
        'foods_to_avoid': 'peanuts',
      };

      final goal = UserGoal.fromJson(json);

      expect(goal.id, 1);
      expect(goal.goalType, 'build_muscle');
      expect(goal.targetWeight, 78.5);
      expect(goal.targetDate, '2026-12-31');
      expect(goal.activityLevel, 'moderately_active');
      expect(goal.trainingDaysPerWeek, 4);
      expect(goal.trainingExperience, 'intermediate');
      expect(goal.availableEquipment, 'barbell, dumbbell, machines');
      expect(goal.dietaryPreference, 'omnivore');
      expect(goal.foodsToAvoid, 'peanuts');

      expect(goal.hasGoal, isTrue);
      expect(goal.equipmentList, ['barbell', 'dumbbell', 'machines']);

      final serialized = goal.toJson();
      expect(serialized['goal_type'], 'build_muscle');
      expect(serialized['target_weight'], 78.5);
      expect(serialized['available_equipment'], 'barbell, dumbbell, machines');
    });

    test('empty goal behavior', () {
      const goal = UserGoal.empty();
      expect(goal.hasGoal, isFalse);
      expect(goal.equipmentList, isEmpty);

      final emptyJson = <String, dynamic>{};
      final fromEmpty = UserGoal.fromJson(emptyJson);
      expect(fromEmpty.hasGoal, isFalse);
      expect(fromEmpty.equipmentList, isEmpty);
    });

    test('goal with integer weight parses to double', () {
      final json = {
        'id': 2,
        'target_weight': 80,
      };
      final goal = UserGoal.fromJson(json);
      expect(goal.targetWeight, 80.0);
    });
  });

  group('DailySummary Model', () {
    test('fromJson parses values', () {
      final json = {
        'date': '2026-10-19',
        'calories_in': 2100,
        'calories_out': 550,
        'net_calories': 1550,
      };

      final summary = DailySummary.fromJson(json);
      expect(summary.date, '2026-10-19');
      expect(summary.caloriesIn, 2100);
      expect(summary.caloriesOut, 550);
      expect(summary.netCalories, 1550);
      expect(summary.caloriesInDouble, 2100.0);
      expect(summary.caloriesOutDouble, 550.0);
      expect(summary.netCaloriesDouble, 1550.0);
    });

    test('DailySummary.empty constructor', () {
      const s = DailySummary.empty('2026-10-19');
      expect(s.date, '2026-10-19');
      expect(s.caloriesIn, 0);
      expect(s.caloriesOut, 0);
      expect(s.netCalories, 0);
    });
  });

  group('UserProfile Model', () {
    test('BMI calculation and formatting', () {
      final user = UserProfile(
        id: 10,
        username: 'alex',
        weight: 70.0,
        height: 175.0,
        birthdate: '1995-05-15',
        age: 31,
      );

      // BMI = 70 / (1.75 * 1.75) = 22.857... -> 22.9
      expect(user.bmi, isNotNull);
      expect(user.bmi!, closeTo(22.86, 0.05));
      expect(user.formattedBmi, '22.9');
    });

    test('BMI handles null or invalid values safely', () {
      const userNoWeight = UserProfile(id: 1, username: 'test', height: 180);
      expect(userNoWeight.bmi, isNull);
      expect(userNoWeight.formattedBmi, '—');

      const userZeroHeight = UserProfile(id: 2, username: 'test', weight: 80, height: 0);
      expect(userZeroHeight.bmi, isNull);
      expect(userZeroHeight.formattedBmi, '—');
    });
  });

  group('Habit & HabitActivityDay Models', () {
    test('Habit fromJson handles defaults', () {
      final habit = Habit.fromJson({
        'id': 5,
        'name': 'Drink Water',
      });
      expect(habit.id, 5);
      expect(habit.name, 'Drink Water');
      expect(habit.frequency, 'daily');
      expect(habit.targetPerWeek, 7);
      expect(habit.color, '#6366F1');
    });

    test('HabitActivityDay parses lists of ids', () {
      final day = HabitActivityDay.fromJson({
        'date': '2026-10-19',
        'completed_habit_ids': [1, 3],
        'pending_habit_ids': [2],
      });
      expect(day.date, '2026-10-19');
      expect(day.completedHabitIds, [1, 3]);
      expect(day.pendingHabitIds, [2]);
    });
  });

  group('Meal & Exercise Models', () {
    test('Meal and MealItem fromJson', () {
      final meal = Meal.fromJson({
        'id': 42,
        'date': '2026-10-19',
        'meal_type': 'lunch',
        'calories': 650.0,
        'protein': 45.0,
        'carbs': 60.0,
        'fat': 20.0,
        'items': [
          {
            'id': 101,
            'food_id': 201,
            'food_name': 'Chicken Breast',
            'quantity': 200,
            'unit': 'g',
            'gram_weight': 200,
            'calories': 330,
            'protein': 62,
            'carbs': 0,
            'fat': 7.2,
          }
        ]
      });

      expect(meal.id, 42);
      expect(meal.mealType, 'lunch');
      expect(meal.items.length, 1);
      expect(meal.items[0].foodName, 'Chicken Breast');
      expect(meal.items[0].foodKind, 'catalog');
      expect(meal.items[0].protein, 62.0);
    });

    test('FoodItem kind, CustomFoodInput toJson, and MealItem foodKind', () {
      final food = FoodItem.fromJson({
        'id': 7,
        'name': 'Homemade Stew',
        'kind': 'custom',
        'avoided': true,
        'calories_per_100g': 150,
        'protein_per_100g': 10,
        'carbs_per_100g': 12,
        'fat_per_100g': 6,
      });
      expect(food.kind, 'custom');
      expect(food.avoided, true);

      final defaultKindFood = FoodItem.fromJson({
        'id': 8,
        'name': 'Apple',
        'calories_per_100g': 52,
        'protein_per_100g': 0.3,
        'carbs_per_100g': 14,
        'fat_per_100g': 0.2,
      });
      expect(defaultKindFood.kind, 'catalog');
      expect(defaultKindFood.avoided, false);

      const input = CustomFoodInput(
        name: 'Oats',
        basis: 'serving',
        servingGrams: 50,
        servingName: 'bowl',
        calories: 185,
        protein: 6.5,
        carbs: 33,
        fat: 3.2,
      );
      expect(input.toJson(), {
        'name': 'Oats',
        'basis': 'serving',
        'serving_grams': 50.0,
        'serving_name': 'bowl',
        'calories': 185.0,
        'protein': 6.5,
        'carbs': 33.0,
        'fat': 3.2,
      });

      final quickItem = MealItem.fromJson({
        'id': 1,
        'food_id': 9,
        'food_name': 'Lunch estimate',
        'food_kind': 'quick',
        'quantity': 1,
        'unit': 'entry',
        'gram_weight': 100,
        'calories': 700,
        'protein': 0,
        'carbs': 0,
        'fat': 0,
      });
      expect(quickItem.foodKind, 'quick');
    });

    test('Exercise fromJson handles numeric types', () {
      final exercise = Exercise.fromJson({
        'id': 12,
        'date': '2026-10-19',
        'name': 'Bench Press',
        'category': 'chest',
        'sets': 4,
        'reps': 10,
        'weight_kg': 80,
        'calories_burned': 120,
      });

      expect(exercise.id, 12);
      expect(exercise.name, 'Bench Press');
      expect(exercise.weightKg, 80.0);
      expect(exercise.caloriesBurned, 120.0);
      expect(exercise.isPr, isFalse);

      final prEx = Exercise.fromJson({
        'id': 13,
        'date': '2026-10-20',
        'name': 'Bench Press',
        'category': 'strength',
        'sets': 3,
        'reps': 8,
        'weight_kg': 85,
        'calories_burned': 110,
        'is_pr': true,
      });
      expect(prEx.isPr, isTrue);

      final hist = ExerciseHistory.fromJson({
        'last': {
          'id': 13,
          'date': '2026-10-20',
          'name': 'Bench Press',
          'category': 'strength',
          'sets': 3,
          'reps': 8,
          'weight_kg': 85,
          'calories_burned': 110,
        },
        'best_weight_kg': 85.0,
        'best_est_1rm': 107.7,
        'times_logged': 5,
      });
      expect(hist.timesLogged, 5);
      expect(hist.bestWeightKg, 85.0);
      expect(hist.bestEst1rm, 107.7);
      expect(hist.last?.id, 13);

      final recItem = RecommendationItem.fromJson({
        'name': 'Bench Press',
        'exercise_catalog_id': 9,
        'category': 'strength',
        'sets': 4,
        'reps': 8,
        'weight_kg': 62.5,
        'rest_seconds': 120,
        'last_performance': 'Last time: 60 kg x 8, 3 days ago',
      });
      expect(recItem.exerciseCatalogId, 9);
      expect(recItem.weightKg, 62.5);
      expect(recItem.restSeconds, 120);
      expect(recItem.lastPerformance, 'Last time: 60 kg x 8, 3 days ago');

      final catItem = ExerciseCatalogItem.fromJson({
        'id': 9,
        'name': 'Bench Press',
        'category': 'strength',
        'default_met': 5.0,
        'equipment': 'barbell',
        'level': 'intermediate',
        'is_custom': false,
        'muscles': [
          {'muscle_group': 'chest', 'role': 'primary'},
          {'muscle_group': 'triceps', 'role': 'secondary'},
        ],
      });
      expect(catItem.equipment, 'barbell');
      expect(catItem.level, 'intermediate');
      expect(catItem.isCustom, isFalse);
      expect(catItem.defaultMet, 5.0);
      expect(catItem.muscles.length, 2);
      expect(catItem.muscles.first.muscleGroup, 'chest');
      expect(catItem.muscles.first.role, 'primary');

      const customEx = CustomExerciseInput(
        name: 'Ring Push-up',
        category: 'strength',
        met: 5.2,
        equipment: 'bodyweight',
        level: 'intermediate',
        description: 'Push-ups on gymnastic rings',
        muscles: [
          ExerciseMuscle(muscleGroup: 'chest', role: 'primary'),
          ExerciseMuscle(muscleGroup: 'triceps', role: 'secondary'),
        ],
      );
      expect(customEx.toJson(), {
        'name': 'Ring Push-up',
        'category': 'strength',
        'met': 5.2,
        'equipment': 'bodyweight',
        'level': 'intermediate',
        'description': 'Push-ups on gymnastic rings',
        'muscles': [
          {'muscle_group': 'chest', 'role': 'primary'},
          {'muscle_group': 'triceps', 'role': 'secondary'},
        ],
      });
    });

    test('missing required id throws FormatException', () {
      expect(() => Exercise.fromJson({'name': 'Running'}),
          throwsA(isA<FormatException>()));
      expect(() => Meal.fromJson({'date': '2026-10-22'}),
          throwsA(isA<FormatException>()));
      expect(() => MealItem.fromJson({'food_id': 1}),
          throwsA(isA<FormatException>()));
      expect(() => FoodItem.fromJson({'name': 'Apple'}),
          throwsA(isA<FormatException>()));
      expect(() => Habit.fromJson({'name': 'Read'}),
          throwsA(isA<FormatException>()));
      expect(() => UserProfile.fromJson({'username': 'alex'}),
          throwsA(isA<FormatException>()));
      expect(() => WeightLog.fromJson({'weight': 75.0}),
          throwsA(isA<FormatException>()));
    });

    test('Recipe preview math and cooking fat regex', () {
      final preview = computeRecipePreview(
        ingredients: const [
          DraftRecipeIngredient(
            foodId: 1,
            foodName: 'White Rice',
            quantity: 300,
            unit: 'g',
            gramWeight: 300,
            calories: 300,
            protein: 6,
            carbs: 66,
            fat: 1,
          ),
          DraftRecipeIngredient(
            foodId: 2,
            foodName: 'Chicken Breast',
            quantity: 100,
            unit: 'g',
            gramWeight: 100,
            calories: 200,
            protein: 30,
            carbs: 0,
            fat: 8,
          ),
        ],
        servings: 4,
      );

      expect(preview.totalGrams, 400);
      expect(preview.totalCalories, 500);
      expect(preview.portionGrams, 100);
      expect(preview.caloriesPerPortion, 125);
      expect(preview.caloriesPer100g, 125);

      final cookedPreview = computeRecipePreview(
        ingredients: const [
          DraftRecipeIngredient(
            foodId: 1,
            foodName: 'White Rice',
            quantity: 300,
            unit: 'g',
            gramWeight: 300,
            calories: 300,
            protein: 6,
            carbs: 66,
            fat: 1,
          ),
          DraftRecipeIngredient(
            foodId: 2,
            foodName: 'Chicken Breast',
            quantity: 100,
            unit: 'g',
            gramWeight: 100,
            calories: 200,
            protein: 30,
            carbs: 0,
            fat: 8,
          ),
        ],
        servings: 4,
        cookedWeightG: 500,
      );
      expect(cookedPreview.portionGrams, 125);
      expect(cookedPreview.caloriesPerPortion, 125);
      expect(cookedPreview.caloriesPer100g, 100);

      expect(hasCookingFat(['White Rice', 'Tomato']), isFalse);
      expect(hasCookingFat(['Boiled potato']), isFalse);
      expect(hasCookingFat(['Palm Oil', 'Rice']), isTrue);
      expect(hasCookingFat(['Unsalted butter']), isTrue);
    });
  });

  group('Exercise Effort Rating Model', () {
    test('parses known and unknown effort_rating and resolves labels', () {
      final exKnown = Exercise.fromJson({
        'id': 1,
        'date': '2026-11-06',
        'name': 'Bench Press',
        'category': 'strength',
        'sets': 4,
        'reps': 8,
        'weight_kg': 75.0,
        'effort_rating': 4,
        'calories_burned': 80.0,
      });
      expect(exKnown.effortRating, 4);
      expect(exKnown.effortLabel, 'Hard');
      expect(
        Exercise.effortDescriptions[4],
        'Required considerable effort. Completing more repetitions would be difficult.',
      );

      final exUnknown = Exercise.fromJson({
        'id': 2,
        'date': '2026-11-06',
        'name': 'Bench Press',
        'category': 'strength',
        'sets': 4,
        'reps': 8,
        'weight_kg': 75.0,
        'effort_rating': null,
        'calories_burned': 80.0,
      });
      expect(exUnknown.effortRating, isNull);
      expect(exUnknown.effortLabel, isNull);
      expect(Exercise.effortLabels.keys.toList(), [1, 2, 3, 4, 5]);
    });
  });
}
