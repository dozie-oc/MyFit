import 'package:flutter/foundation.dart';
import 'services/api_client.dart';

class AuthState extends ChangeNotifier {
  String? _token;
  Map<String, dynamic>? _user;
  bool _loading = false;
  String? _error;

  bool _hasGoal = true;
  bool _checkingGoal = false;

  bool get isLoggedIn => _token != null;
  Map<String, dynamic>? get user => _user;
  bool get loading => _loading;
  String? get error => _error;
  bool get hasGoal => _hasGoal;
  bool get checkingGoal => _checkingGoal;

  Future<void> checkGoal() async {
    _checkingGoal = true;
    try {
      final goal = await ApiClient.getGoal();
      _hasGoal = goal['id'] != null ||
          (goal['goal_type'] != null && goal['goal_type'].toString().isNotEmpty);
    } catch (_) {
      _hasGoal = true;
    } finally {
      _checkingGoal = false;
    }
  }

  void markGoalCompleted() {
    _hasGoal = true;
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
      }
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
    required double weight,
    required double height,
    required String birthdate,
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
    _hasGoal = true;
    _checkingGoal = false;
    notifyListeners();
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }
}
