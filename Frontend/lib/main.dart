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

/// A simple notifier that fires whenever its tab becomes the active one.
/// Each screen holds a reference to its own notifier and calls
/// refresh() from its listener. This lets us trigger a fetch whenever
/// the user switches to that tab, without requiring a full widget rebuild.
class TabActivatedNotifier extends ChangeNotifier {
  void activate() => notifyListeners();
}

class MainShell extends StatefulWidget {
  final AuthState authState;
  const MainShell({super.key, required this.authState});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  // One notifier per tab — fired when the user navigates to that tab.
  final List<TabActivatedNotifier> _tabNotifiers = List.generate(
    6,
    (_) => TabActivatedNotifier(),
  );

  late final List<
      ({String label, IconData icon, IconData activeIcon, Widget screen})> _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = [
      (
        label: 'Today',
        icon: Icons.home_outlined,
        activeIcon: Icons.home,
        screen: DashboardScreen(
          user: widget.authState.user ?? {},
          tabNotifier: _tabNotifiers[0],
        ),
      ),
      (
        label: 'Foods',
        icon: Icons.search_outlined,
        activeIcon: Icons.search,
        screen: FoodsScreen(tabNotifier: _tabNotifiers[1]),
      ),
      (
        label: 'Meals',
        icon: Icons.restaurant_outlined,
        activeIcon: Icons.restaurant,
        screen: MealsScreen(tabNotifier: _tabNotifiers[2]),
      ),
      (
        label: 'Exercise',
        icon: Icons.fitness_center_outlined,
        activeIcon: Icons.fitness_center,
        screen: ExercisesScreen(tabNotifier: _tabNotifiers[3]),
      ),
      (
        label: 'Habits',
        icon: Icons.checklist_outlined,
        activeIcon: Icons.checklist,
        screen: HabitsScreen(tabNotifier: _tabNotifiers[4]),
      ),
      (
        label: 'Profile',
        icon: Icons.person_outline,
        activeIcon: Icons.person,
        screen: ProfileScreen(
          authState: widget.authState,
          tabNotifier: _tabNotifiers[5],
        ),
      ),
    ];
  }

  @override
  void dispose() {
    for (final n in _tabNotifiers) {
      n.dispose();
    }
    super.dispose();
  }

  void _onTabSelected(int i) {
    if (i == _index) return;
    setState(() => _index = i);
    // Notify the newly-active tab so its screen can re-fetch stale data.
    _tabNotifiers[i].activate();
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
        onDestinationSelected: _onTabSelected,
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
