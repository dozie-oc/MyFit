import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:myfit_app/models/models.dart';
import 'package:myfit_app/screens/meals_screen.dart';
import 'package:myfit_app/widgets/food_picker_sheet.dart';

void main() {
  const chickenPortionBreast = FoodPortion(
    id: 11,
    name: '1 breast',
    quantity: 1.0,
    unit: 'breast',
    gramWeight: 150.0,
  );

  const chickenFood = FoodItem(
    id: 1,
    name: 'Chicken Breast',
    caloriesPer100g: 165.0,
    proteinPer100g: 31.0,
    carbsPer100g: 0.0,
    fatPer100g: 3.6,
    portions: [chickenPortionBreast],
  );

  const ricePortionCup = FoodPortion(
    id: 21,
    name: '1 cup cooked',
    quantity: 1.0,
    unit: 'cup',
    gramWeight: 200.0,
  );

  const ricePortionBowl = FoodPortion(
    id: 22,
    name: '1 large bowl',
    quantity: 1.0,
    unit: 'bowl',
    gramWeight: 300.0,
  );

  const riceFood = FoodItem(
    id: 2,
    name: 'White Rice',
    caloriesPer100g: 130.0,
    proteinPer100g: 2.7,
    carbsPer100g: 28.0,
    fatPer100g: 0.3,
    portions: [ricePortionCup, ricePortionBowl],
  );

  const salmonFood = FoodItem(
    id: 3,
    name: 'Atlantic Salmon',
    caloriesPer100g: 208.0,
    proteinPer100g: 20.0,
    carbsPer100g: 0.0,
    fatPer100g: 13.0,
  );

  group('DraftMealItem & computeMealTotals unit tests', () {
    test('recalculates nutrition when food, portion, unit, or quantity changes',
        () {
      // Start with 100g Chicken Breast: 165 kcal, 31P, 0C, 3.6F
      var item1 = const DraftMealItem(
        food: chickenFood,
        quantity: 100,
        unit: 'g',
      );
      // Start with 1 cup White Rice (200g): 260 kcal, 5.4P, 56C, 0.6F
      var item2 = DraftMealItem(
        food: riceFood,
        quantity: 1,
        portionId: ricePortionCup.id,
        portionName: ricePortionCup.name,
        portionGramWeight: ricePortionCup.gramWeight,
        portionBaseQuantity: ricePortionCup.quantity,
        unit: ricePortionCup.unit,
      );

      var totals = computeMealTotals([item1, item2]);
      expect(totals.totalGrams, closeTo(300.0, 0.01));
      expect(totals.calories, closeTo(425.0, 0.01));
      expect(totals.protein, closeTo(36.4, 0.01));
      expect(totals.carbs, closeTo(56.0, 0.01));
      expect(totals.fat, closeTo(4.2, 0.01));

      // Change portion on rice from 1 cup (200g) to 1 large bowl (300g)
      // Rice is now 390 kcal, 8.1P, 84C, 0.9F
      item2 = item2.withPortion(ricePortionBowl, quantity: 1);
      totals = computeMealTotals([item1, item2]);
      expect(totals.totalGrams, closeTo(400.0, 0.01));
      expect(totals.calories, closeTo(555.0, 0.01));
      expect(totals.protein, closeTo(39.1, 0.01));
      expect(totals.carbs, closeTo(84.0, 0.01));

      // Change unit on chicken from 100g to 0.2 kg (200g)
      // Chicken is now 330 kcal, 62P, 0C, 7.2F
      item1 = item1.withUnit('kg', quantity: 0.2);
      expect(item1.gramWeight, closeTo(200.0, 0.01));
      totals = computeMealTotals([item1, item2]);
      expect(totals.totalGrams, closeTo(500.0, 0.01));
      expect(totals.calories, closeTo(720.0, 0.01));
      expect(totals.protein, closeTo(70.1, 0.01));

      // Change food on item1 from Chicken to Salmon (100g: 208 kcal, 20P, 0C, 13F)
      item1 = item1.withFood(salmonFood, unit: 'g', quantity: 100);
      totals = computeMealTotals([item1, item2]);
      expect(totals.totalGrams, closeTo(400.0, 0.01));
      expect(totals.calories, closeTo(598.0, 0.01));
      expect(totals.protein, closeTo(28.1, 0.01));
      expect(totals.fat, closeTo(13.9, 0.01));

      // Remove item2 -> only item1 remains
      totals = computeMealTotals([item1]);
      expect(totals.totalGrams, closeTo(100.0, 0.01));
      expect(totals.calories, closeTo(208.0, 0.01));
    });

    test('unsaved draft edits do not alter existing saved Meal object', () {
      const savedMeal = Meal(
        id: 42,
        date: '2026-04-10',
        mealType: 'lunch',
        calories: 425.0,
        protein: 36.4,
        carbs: 56.0,
        fat: 4.2,
        items: [
          MealItem(
            id: 101,
            foodId: 1,
            foodName: 'Chicken Breast',
            quantity: 100,
            unit: 'g',
            gramWeight: 100,
            calories: 165.0,
            protein: 31.0,
            carbs: 0.0,
            fat: 3.6,
          ),
          MealItem(
            id: 102,
            foodId: 2,
            foodName: 'White Rice',
            portionId: 21,
            portionName: '1 cup cooked',
            quantity: 1,
            unit: 'cup',
            gramWeight: 200,
            calories: 260.0,
            protein: 5.4,
            carbs: 56.0,
            fat: 0.6,
          ),
        ],
      );

      final draftItems = savedMeal.items
          .map((it) => DraftMealItem.fromMealItem(it))
          .toList();
      draftItems[0] = draftItems[0].withFood(salmonFood, quantity: 250, unit: 'g');
      draftItems.removeAt(1);

      // Saved meal remains untouched
      expect(savedMeal.calories, 425.0);
      expect(savedMeal.items.length, 2);
      expect(savedMeal.items[0].foodName, 'Chicken Breast');
      expect(savedMeal.items[0].gramWeight, 100.0);
    });
  });

  group('MealEditorScreen widget tests', () {
    testWidgets(
        'supports changing food, portion, unit, quantity, removing items, and live recalculation',
        (tester) async {
      final initialItems = [
        const DraftMealItem(
          food: chickenFood,
          quantity: 100,
          unit: 'g',
        ),
        DraftMealItem(
          food: riceFood,
          quantity: 1,
          portionId: ricePortionCup.id,
          portionName: ricePortionCup.name,
          portionGramWeight: ricePortionCup.gramWeight,
          portionBaseQuantity: ricePortionCup.quantity,
          unit: ricePortionCup.unit,
        ),
      ];

      Map<String, dynamic>? submittedPayload;

      await tester.pumpWidget(
        MaterialApp(
          home: MealEditorScreen(
            initialItems: initialItems,
            loadCatalogOnInit: false,
            onPickFood: (ctx, existing) async {
              // Simulate changing Chicken Breast to 100g Atlantic Salmon
              return const PickedFoodItem(
                food: salmonFood,
                quantity: 100,
                unit: 'g',
                gramWeight: 100,
              );
            },
            onSubmitMeal: (payload, existingId) async {
              submittedPayload = payload;
            },
          ),
        ),
      );

      // Initial totals: 100g Chicken (165 kcal) + 1 cup Rice 200g (260 kcal) = 425 kcal, 300g
      expect(find.byKey(const Key('meal-totals-weight')), findsOneWidget);
      expect(find.text('2 items · 300g'), findsOneWidget);
      expect(find.text('425'), findsOneWidget);

      // 1. Change quantity of Chicken from 100g to 200g -> Chicken = 330 kcal, Total = 590 kcal, 400g
      await tester.enterText(find.byKey(const Key('item-qty-0')), '200');
      await tester.pump();
      expect(find.text('2 items · 400g'), findsOneWidget);
      expect(find.text('590'), findsOneWidget);

      // 2. Change portion of Rice from '1 cup cooked (200g)' to '1 large bowl (300g)'
      // Rice = 390 kcal, Total = 330 + 390 = 720 kcal, 500g
      final riceDropdown = find.byKey(const Key('item-unit-portion-1-portion:21'));
      await tester.ensureVisible(riceDropdown);
      await tester.pumpAndSettle();
      await tester.tap(riceDropdown);
      await tester.pumpAndSettle();
      await tester.tap(find.text('1 large bowl (300g)').last);
      await tester.pumpAndSettle();
      expect(find.text('2 items · 500g'), findsOneWidget);
      expect(find.text('720'), findsOneWidget);

      // 3. Change food on item 0 (Chicken -> 100g Salmon: 208 kcal)
      // Total = 208 + 390 = 598 kcal, 400g
      final changeFoodBtn = find.byKey(const Key('change-food-0'));
      await tester.ensureVisible(changeFoodBtn);
      await tester.pumpAndSettle();
      await tester.tap(changeFoodBtn);
      await tester.pumpAndSettle();
      expect(find.text('Atlantic Salmon'), findsOneWidget);
      expect(find.text('2 items · 400g'), findsOneWidget);
      expect(find.text('598'), findsOneWidget);

      // 4. Remove item 1 (Rice) -> only 100g Salmon remains (208 kcal, 100g)
      final removeRiceBtn = find.byKey(const Key('remove-item-1'));
      await tester.ensureVisible(removeRiceBtn);
      await tester.pumpAndSettle();
      await tester.tap(removeRiceBtn);
      await tester.pumpAndSettle();
      expect(find.text('1 item · 100g'), findsOneWidget);
      expect(find.text('208'), findsOneWidget);

      // 5. Change unit on Salmon from Grams (g) to Kilograms (kg) and set quantity to 0.5 kg (500g, 1040 kcal)
      final salmonDropdown = find.byKey(const Key('item-unit-portion-0-unit:g'));
      await tester.ensureVisible(salmonDropdown);
      await tester.pumpAndSettle();
      await tester.tap(salmonDropdown);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Kilograms (kg)').last);
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('item-qty-0')), '0.5');
      await tester.pump();
      expect(find.text('1 item · 500g'), findsOneWidget);
      expect(find.text('1040'), findsOneWidget);

      // 6. Save meal and verify payload
      await tester.tap(find.byKey(const Key('save-meal-button')));
      await tester.pumpAndSettle();
      expect(submittedPayload, isNotNull);
      final items = submittedPayload!['items'] as List<dynamic>;
      expect(items.length, 1);
      expect(items.first['food_id'], salmonFood.id);
      expect(items.first['quantity'], 0.5);
      expect(items.first['unit'], 'kg');
    });
  });
}
