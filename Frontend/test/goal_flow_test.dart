import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:myfit_app/auth_state.dart';
import 'package:myfit_app/main.dart';
import 'package:myfit_app/models/models.dart';
import 'package:myfit_app/screens/goal_screen.dart';
import 'package:myfit_app/services/api_client.dart';
import 'package:myfit_app/theme.dart';

void main() {
  group('AuthState checkGoal() Unit Tests', () {
    test('success: goal exists sets GoalStatus.exists and hasGoal to true', () async {
      final authState = AuthState(
        initialToken: 'valid_token',
        getGoal: () async => const UserGoal(
          id: 1,
          goalType: 'build_muscle',
          targetWeight: 80.0,
        ),
      );

      expect(authState.goalStatus, GoalStatus.loading);
      await authState.checkGoal();

      expect(authState.goalStatus, GoalStatus.exists);
      expect(authState.hasGoal, isTrue);
      expect(authState.goalError, isNull);
      expect(authState.checkingGoal, isFalse);
    });

    test('missing goal: sets GoalStatus.noGoal and hasGoal to false', () async {
      final authState = AuthState(
        initialToken: 'valid_token',
        getGoal: () async => const UserGoal.empty(),
      );

      await authState.checkGoal();

      expect(authState.goalStatus, GoalStatus.noGoal);
      expect(authState.hasGoal, isFalse);
      expect(authState.goalError, isNull);
      expect(authState.checkingGoal, isFalse);
    });

    test('API failure: ApiException sets GoalStatus.error and does not mark hasGoal', () async {
      final authState = AuthState(
        initialToken: 'valid_token',
        getGoal: () async => throw const ApiException(500, 'Internal Server Error'),
      );

      await authState.checkGoal();

      expect(authState.goalStatus, GoalStatus.error);
      expect(authState.hasGoal, isFalse);
      expect(authState.goalError, 'Internal Server Error');
      expect(authState.checkingGoal, isFalse);
    });

    test('API failure: generic network error sets GoalStatus.error', () async {
      final authState = AuthState(
        initialToken: 'valid_token',
        getGoal: () async => throw Exception('Socket connection timeout'),
      );

      await authState.checkGoal();

      expect(authState.goalStatus, GoalStatus.error);
      expect(authState.hasGoal, isFalse);
      expect(authState.goalError, contains('Socket connection timeout'));
      expect(authState.checkingGoal, isFalse);
    });

    test('retry after API failure successfully updates to exists when goal returns', () async {
      var fail = true;
      final authState = AuthState(
        initialToken: 'valid_token',
        getGoal: () async {
          if (fail) {
            throw const ApiException(503, 'Service Unavailable');
          }
          return const UserGoal(id: 10, goalType: 'lose_weight');
        },
      );

      // First attempt fails
      await authState.checkGoal();
      expect(authState.goalStatus, GoalStatus.error);
      expect(authState.hasGoal, isFalse);

      // Second attempt succeeds
      fail = false;
      await authState.checkGoal();
      expect(authState.goalStatus, GoalStatus.exists);
      expect(authState.hasGoal, isTrue);
      expect(authState.goalError, isNull);
    });
  });

  group('MyFitApp UI Navigation & Goal Flow Widget Tests', () {
    testWidgets('loading state displays CircularProgressIndicator and not MainShell',
        (tester) async {
      final authState = AuthState(
        initialToken: 'token',
        initialGoalStatus: GoalStatus.loading,
      );

      await tester.pumpWidget(MyFitApp(authState: authState));
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.byType(MainShell), findsNothing);
      expect(find.byType(GoalScreen), findsNothing);
    });

    testWidgets('goal exists displays MainShell', (tester) async {
      final authState = AuthState(
        initialToken: 'token',
        initialUser: const UserProfile(id: 1, username: 'testuser'),
        initialGoalStatus: GoalStatus.exists,
      );

      await tester.pumpWidget(MyFitApp(authState: authState));
      await tester.pump();

      expect(find.byType(MainShell), findsOneWidget);
      expect(find.byType(GoalScreen), findsNothing);
      expect(find.byType(ErrorView), findsNothing);
    });

    testWidgets('user without goal is directed to goal setup flow (GoalScreen onboarding)',
        (tester) async {
      tester.view.physicalSize = const Size(800, 2400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final authState = AuthState(
        initialToken: 'token',
        initialUser: const UserProfile(id: 1, username: 'newuser'),
        initialGoalStatus: GoalStatus.noGoal,
      );

      await tester.pumpWidget(MyFitApp(authState: authState));
      await tester.pump();

      expect(find.byType(GoalScreen), findsOneWidget);
      expect(find.text('Set Up Your Goal'), findsOneWidget);
      expect(find.byType(MainShell), findsNothing);
      expect(find.byType(ErrorView), findsNothing);
    });

    testWidgets('API failure displays ErrorView and does NOT silently allow access to MainShell',
        (tester) async {
      final authState = AuthState(
        initialToken: 'token',
        initialUser: const UserProfile(id: 1, username: 'testuser'),
        initialGoalStatus: GoalStatus.error,
        initialGoalError: 'Connection to server failed',
      );

      await tester.pumpWidget(MyFitApp(authState: authState));
      await tester.pump();

      // Verifies acceptance criteria: API failure does not silently allow access
      expect(find.byType(ErrorView), findsOneWidget);
      expect(find.text('Connection to server failed'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      expect(find.byType(MainShell), findsNothing);
      expect(find.byType(GoalScreen), findsNothing);
    });

    testWidgets('tapping Retry on API failure re-checks goal and recovers to MainShell',
        (tester) async {
      var callCount = 0;
      final authState = AuthState(
        initialToken: 'token',
        initialUser: const UserProfile(id: 1, username: 'testuser'),
        initialGoalStatus: GoalStatus.error,
        initialGoalError: 'Network glitch',
        getGoal: () async {
          callCount++;
          return const UserGoal(id: 1, goalType: 'maintain_weight');
        },
      );

      await tester.pumpWidget(MyFitApp(authState: authState));
      await tester.pump();

      expect(find.byType(ErrorView), findsOneWidget);

      // Tap Retry button
      await tester.tap(find.text('Retry'));
      await tester.pump();

      expect(callCount, 1);
      expect(authState.goalStatus, GoalStatus.exists);
      expect(find.byType(MainShell), findsOneWidget);
      expect(find.byType(ErrorView), findsNothing);
    });
  });
}
