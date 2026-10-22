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
      expect(meal.items[0].protein, 62.0);
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
  });
}
