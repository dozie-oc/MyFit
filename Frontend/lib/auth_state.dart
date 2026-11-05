import 'package:flutter/foundation.dart';
import 'models/models.dart';
import 'services/api_client.dart';

enum GoalStatus {
  loading,
  exists,
  noGoal,
  error,
}

class AuthState extends ChangeNotifier {
  final Future<UserGoal> Function() _getGoal;

  String? _token;
  UserProfile? _user;
  bool _loading = false;
  String? _error;

  GoalStatus _goalStatus;
  String? _goalError;
  bool _checkingGoal = false;

  bool get isLoggedIn => _token != null;
  UserProfile? get user => _user;
  bool get loading => _loading;
  String? get error => _error;
  GoalStatus get goalStatus => _goalStatus;
  bool get hasGoal => _goalStatus == GoalStatus.exists;
  bool get checkingGoal => _checkingGoal;
  String? get goalError => _goalError;

  AuthState({
    Future<UserGoal> Function()? getGoal,
    @visibleForTesting String? initialToken,
    @visibleForTesting UserProfile? initialUser,
    @visibleForTesting GoalStatus initialGoalStatus = GoalStatus.loading,
    @visibleForTesting String? initialGoalError,
    @visibleForTesting bool initialCheckingGoal = false,
  })  : _getGoal = getGoal ?? ApiClient.getGoal,
        _token = initialToken,
        _user = initialUser,
        _goalStatus = initialGoalStatus,
        _goalError = initialGoalError,
        _checkingGoal = initialCheckingGoal {
    ApiClient.onUnauthorized = () {
      if (_token != null) logout();
    };
  }

  Future<void> checkGoal() async {
    if (_checkingGoal) return;
    _checkingGoal = true;
    _goalStatus = GoalStatus.loading;
    _goalError = null;
    notifyListeners();
    try {
      final goal = await _getGoal();
      _goalStatus = goal.hasGoal ? GoalStatus.exists : GoalStatus.noGoal;
      _goalError = null;
    } on ApiException catch (e) {
      _goalStatus = GoalStatus.error;
      _goalError = e.message;
    } catch (e) {
      _goalStatus = GoalStatus.error;
      _goalError = 'Connection failed: $e';
    } finally {
      _checkingGoal = false;
      notifyListeners();
    }
  }

  void markGoalCompleted() {
    _goalStatus = GoalStatus.exists;
    _goalError = null;
    notifyListeners();
  }

  void markGoalIncomplete() {
    _goalStatus = GoalStatus.noGoal;
    _goalError = null;
    notifyListeners();
  }

  // Restore session on app start
  Future<void> restore() async {
    _token = await ApiClient.getToken();
    if (_token != null) {
      try {
        _user = await ApiClient.me();
        await checkGoal();
      } catch (_) {
        _token = null;
        await ApiClient.clearToken();
        _checkingGoal = false;
        _goalStatus = GoalStatus.loading;
      }
    } else {
      _checkingGoal = false;
      _goalStatus = GoalStatus.loading;
    }
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _token = await ApiClient.login(username, password);
      _user = await ApiClient.me();
      await checkGoal();
      _loading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      _loading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _error = 'Connection failed: $e';
      _loading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> adminLogin() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _token = await ApiClient.adminLogin();
      _user = await ApiClient.me();
      await checkGoal();
      _loading = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      _loading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _error = 'Connection failed: $e';
      _loading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> register({
    required String username,
    required String password,
    double? weight,
    double? height,
    String? birthdate,
  }) async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      await ApiClient.register(
        username: username,
        password: password,
        weight: weight,
        height: height,
        birthdate: birthdate,
      );
      return await login(username, password);
    } on ApiException catch (e) {
      _error = e.message;
      _loading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _error = 'Connection failed: $e';
      _loading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await ApiClient.clearToken();
    _token = null;
    _user = null;
    _goalStatus = GoalStatus.loading;
    _checkingGoal = false;
    _goalError = null;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
