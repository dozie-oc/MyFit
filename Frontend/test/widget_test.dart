import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:myfit_app/models/models.dart';
import 'package:myfit_app/screens/goal_screen.dart';
import 'package:myfit_app/screens/profile_screen.dart' show GoalCard;
import 'package:myfit_app/theme.dart';

void main() {
  group('GoalCard Widget Tests', () {
    testWidgets('renders empty state when no goal is set', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme,
          home: const Scaffold(
            body: GoalCard(goal: UserGoal.empty()),
          ),
        ),
      );

      expect(find.text('No goal set yet.'), findsOneWidget);
      expect(
        find.text(
          'Tap Edit above to set your fitness goal and get personalised recommendations.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('renders populated goal with details', (tester) async {
      const goal = UserGoal(
        id: 1,
        goalType: 'build_muscle',
        activityLevel: 'moderately_active',
        trainingDaysPerWeek: 4,
        trainingExperience: 'intermediate',
        targetWeight: 82.5,
        dietaryPreference: 'omnivore',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme,
          home: const Scaffold(
            body: GoalCard(goal: goal),
          ),
        ),
      );

      expect(find.text('Build Muscle'), findsOneWidget);
      expect(find.text('Moderately Active'), findsOneWidget);
      expect(find.text('4 days'), findsOneWidget);
      expect(find.text('Intermediate'), findsOneWidget);
      expect(find.text('82.5kg'), findsOneWidget);
      expect(find.text('Omnivore'), findsOneWidget);
    });
  });

  group('GoalScreen Widget Tests', () {
    testWidgets('renders onboarding mode with greeting and action buttons',
        (tester) async {
      tester.view.physicalSize = const Size(800, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme,
          home: const GoalScreen(
            isOnboarding: true,
            initialGoal: UserGoal.empty(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Set Up Your Goal'), findsOneWidget);
      expect(find.text('Body Measurements (optional)'), findsOneWidget);
      expect(find.text('What is your primary goal?'), findsOneWidget);
      expect(find.text('Lose Weight'), findsOneWidget);
      expect(find.text('Build Muscle'), findsOneWidget);
      expect(find.text('Get started →'), findsOneWidget);
      expect(find.text('Skip for now'), findsOneWidget);
    });

    testWidgets('renders standard settings mode', (tester) async {
      tester.view.physicalSize = const Size(800, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme,
          home: const GoalScreen(
            isOnboarding: false,
            initialGoal: UserGoal.empty(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Fitness Goal'), findsOneWidget);
      expect(find.text('Save goal'), findsOneWidget);
      expect(find.text('Skip for now'), findsNothing);
    });

    testWidgets('allows selecting goal type chip', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: appTheme,
          home: const GoalScreen(
            isOnboarding: false,
            initialGoal: UserGoal.empty(),
          ),
        ),
      );

      await tester.pumpAndSettle();

      final buildMuscleFinder = find.text('Build Muscle');
      expect(buildMuscleFinder, findsOneWidget);

      await tester.tap(buildMuscleFinder);
      await tester.pumpAndSettle();

      // Selection state changes visual styling without errors
      expect(buildMuscleFinder, findsOneWidget);
    });
  });
}
