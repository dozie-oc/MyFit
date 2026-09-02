import 'package:flutter/material.dart';
import 'auth_state.dart';
import 'theme.dart';
import 'screens/auth_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/foods_screen.dart';
import 'screens/meals_screen.dart';
import 'screens/exercises_screen.dart';
import 'screens/habits_screen.dart';
import 'screens/profile_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final authState = AuthState();
  await authState.restore();
  runApp(MyFitApp(authState: authState));
}

class MyFitApp extends StatelessWidget {
  final AuthState authState;
  const MyFitApp({super.key, required this.authState});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: authState,
      builder: (context, _) {
        return MaterialApp(
          title: 'MyFit',
          theme: appTheme,
          debugShowCheckedModeBanner: false,
          home: authState.isLoggedIn
              ? MainShell(authState: authState)
              : LoginScreen(authState: authState),
        );
      },
    );
  }
}

// ─────────────────────────────────────────
// MAIN SHELL — bottom nav (6 tabs)
// ─────────────────────────────────────────

class MainShell extends StatefulWidget {
  final AuthState authState;
  const MainShell({super.key, required this.authState});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  late final List<({String label, IconData icon, IconData activeIcon, Widget screen})> _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = [
      (
        label: 'Today',
        icon: Icons.home_outlined,
        activeIcon: Icons.home,
        screen: DashboardScreen(user: widget.authState.user ?? {}),
      ),
      (
        label: 'Foods',
        icon: Icons.search_outlined,
        activeIcon: Icons.search,
        screen: const FoodsScreen(),
      ),
      (
        label: 'Meals',
        icon: Icons.restaurant_outlined,
        activeIcon: Icons.restaurant,
        screen: const MealsScreen(),
      ),
      (
        label: 'Exercise',
        icon: Icons.fitness_center_outlined,
        activeIcon: Icons.fitness_center,
        screen: const ExercisesScreen(),
      ),
      (
        label: 'Habits',
        icon: Icons.checklist_outlined,
        activeIcon: Icons.checklist,
        screen: const HabitsScreen(),
      ),
      (
        label: 'Profile',
        icon: Icons.person_outline,
        activeIcon: Icons.person,
        screen: ProfileScreen(authState: widget.authState),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: _tabs.map((t) => t.screen).toList(),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        indicatorColor:
            Theme.of(context).colorScheme.primary.withValues(alpha: 0.12),
        backgroundColor: Colors.white,
        destinations: _tabs
            .map((t) => NavigationDestination(
                  icon: Icon(t.icon),
                  selectedIcon: Icon(t.activeIcon,
                      color: Theme.of(context).colorScheme.primary),
                  label: t.label,
                ))
            .toList(),
      ),
    );
  }
}
