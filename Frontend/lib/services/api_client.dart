import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

// ─────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────

String get kBaseUrl {
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://127.0.0.1:8000';
}

// ─────────────────────────────────────────
// EXCEPTIONS
// ─────────────────────────────────────────

class ApiException implements Exception {
  final int statusCode;
  final String message;
  const ApiException(this.statusCode, this.message);
  @override
  String toString() => message;
}

// ─────────────────────────────────────────
// HTTP CLIENT HELPER & EVENT BUS
// ─────────────────────────────────────────

class ApiClient {
  static const _tokenKey = 'auth_token';

  /// Global notifier to trigger soft reloads across all active screens
  /// whenever any entity (meal, exercise, habit, food, measurement) is created,
  /// updated, or deleted.
  static final ValueNotifier<int> dataChangeNotifier = ValueNotifier<int>(0);

  static void notifyDataChanged() {
    dataChangeNotifier.value++;
  }

  // ── Token storage ──────────────────────

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  static Future<void> saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  static Future<void> clearToken() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  // ── Auth headers ──────────────────────

  static Future<Map<String, String>> _authHeaders() async {
    final token = await getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  static Uri _uri(String path, [Map<String, String>? params]) {
    final uri = Uri.parse('$kBaseUrl$path');
    if (params != null && params.isNotEmpty) {
      return uri.replace(queryParameters: params);
    }
    return uri;
  }

  static dynamic _decode(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      if (res.body.isEmpty) return null;
      return jsonDecode(res.body);
    }
    String message = 'Request failed (${res.statusCode})';
    try {
      final body = jsonDecode(res.body);
      final detail = body['detail'];
      if (detail is List && detail.isNotEmpty) {
        message = detail.map((e) {
          if (e is Map) {
            final loc = (e['loc'] as List?)?.join('.') ?? '';
            final msg = e['msg'] ?? '';
            return loc.isNotEmpty ? '$loc: $msg' : msg.toString();
          }
          return e.toString();
        }).join('\n');
      } else if (detail != null) {
        message = detail.toString();
      }
    } catch (_) {
      if (res.body.isNotEmpty) {
        message = res.body;
      }
    }
    throw ApiException(res.statusCode, message);
  }

  // ── CRUD helpers ──────────────────────

  static Future<dynamic> get(String path,
      [Map<String, String>? params]) async {
    final res = await http.get(_uri(path, params),
        headers: await _authHeaders());
    return _decode(res);
  }

  static Future<dynamic> post(String path, Map<String, dynamic> body) async {
    final res = await http.post(_uri(path),
        headers: await _authHeaders(), body: jsonEncode(body));
    return _decode(res);
  }

  static Future<dynamic> patch(String path, Map<String, dynamic> body) async {
    final res = await http.patch(_uri(path),
        headers: await _authHeaders(), body: jsonEncode(body));
    return _decode(res);
  }

  static Future<void> delete(String path) async {
    final res =
        await http.delete(_uri(path), headers: await _authHeaders());
    _decode(res);
  }

  // ─────────────────────────────────────
  // AUTH & MEASUREMENTS
  // ─────────────────────────────────────

  static Future<Map<String, dynamic>> register({
    required String username,
    required String password,
    required double weight,
    required double height,
    required String birthdate,
  }) async {
    return await post('/auth/register', {
      'username': username,
      'password': password,
      'weight': weight,
      'height': height,
      'birthdate': birthdate,
    });
  }

  static Future<String> login(String username, String password) async {
    final data = await post('/auth/login', {
      'username': username,
      'password': password,
    });
    final token = data['access_token'] as String;
    await saveToken(token);
    return token;
  }

  static Future<String> adminLogin() async {
    final data = await post('/auth/admin-login', {});
    final token = data['access_token'] as String;
    await saveToken(token);
    return token;
  }

  static Future<Map<String, dynamic>> me() async {
    return await get('/auth/me');
  }

  static Future<Map<String, dynamic>> updateMeasurements({
    double? weight,
    double? height,
  }) async {
    final body = <String, dynamic>{
      'weight': ?weight,
      'height': ?height,
    };
    final data = await patch('/auth/measurements', body);
    notifyDataChanged();
    return data;
  }

  // ─────────────────────────────────────
  // FOODS
  // ─────────────────────────────────────

  static Future<List<dynamic>> getFoods([String? query]) async {
    final params = <String, String>{};
    if (query != null && query.isNotEmpty) params['q'] = query;
    return await get('/foods${query != null ? '/search' : ''}', params);
  }

  static Future<Map<String, dynamic>> getFood(int id) async {
    return await get('/foods/$id');
  }

  static Future<List<dynamic>> searchUsda(String query) async {
    final data = await get('/foods/usda/search', {'q': query});
    if (data is Map && data['foods'] is List) {
      return data['foods'] as List<dynamic>;
    }
    if (data is List) return data;
    return [];
  }

  static Future<Map<String, dynamic>> importUsda(int fdcId) async {
    final res = await post('/foods/usda/$fdcId/import', {});
    notifyDataChanged();
    return res;
  }

  // ─────────────────────────────────────
  // MEALS
  // ─────────────────────────────────────

  static Future<List<dynamic>> getMeals([String? date]) async {
    final params = <String, String>{};
    if (date != null) params['meal_date'] = date;
    return await get('/meals', params);
  }

  static Future<Map<String, dynamic>> createMeal(
      Map<String, dynamic> body) async {
    final res = await post('/meals', body);
    notifyDataChanged();
    return res;
  }

  static Future<void> deleteMeal(int id) async {
    await delete('/meals/$id');
    notifyDataChanged();
  }

  static Future<Map<String, dynamic>> overrideMealCalories(
      int id, double calories) async {
    final res = await patch(
        '/meals/$id/calories', {'override_calories': calories});
    notifyDataChanged();
    return res;
  }

  // ─────────────────────────────────────
  // EXERCISES & CATALOG
  // ─────────────────────────────────────

  static Future<List<dynamic>> getExerciseCatalog([String? category]) async {
    final params = <String, String>{};
    if (category != null && category.isNotEmpty) {
      params['category'] = category;
    }
    return await get('/exercises/catalog', params);
  }

  static Future<List<dynamic>> getExercises([String? date]) async {
    final params = <String, String>{};
    if (date != null) params['exercise_date'] = date;
    return await get('/exercises', params);
  }

  static Future<Map<String, dynamic>> createExercise(
      Map<String, dynamic> body) async {
    final res = await post('/exercises', body);
    notifyDataChanged();
    return res;
  }

  static Future<void> deleteExercise(int id) async {
    await delete('/exercises/$id');
    notifyDataChanged();
  }

  // ─────────────────────────────────────
  // WEIGHT
  // ─────────────────────────────────────

  static Future<List<dynamic>> getWeightLogs() async {
    return await get('/weight');
  }

  static Future<Map<String, dynamic>> logWeight(
      String date, double weight) async {
    final res = await post('/weight', {'date': date, 'weight': weight});
    notifyDataChanged();
    return res;
  }

  // ─────────────────────────────────────────
  // HABITS
  // ─────────────────────────────────────────

  /// Returns all habits with embedded logs (last 35 days).
  /// This is the primary endpoint — avoids N+1 log fetches.
  static Future<List<dynamic>> getHabits([int days = 35]) async {
    return await get('/habits', {'days': days.toString()});
  }

  static Future<Map<String, dynamic>> createHabit(
    String name, {
    String? description,
    String? color,
    int targetPerWeek = 7,
  }) async {
    final res = await post('/habits', {
      'name': name,
      'description': ?description,
      'color': ?color,
      'target_per_week': targetPerWeek,
    });
    notifyDataChanged();
    return res;
  }

  static Future<Map<String, dynamic>> updateHabit(
    int id, {
    String? name,
    String? description,
    String? color,
    int? targetPerWeek,
  }) async {
    final body = <String, dynamic>{
      'name': ?name,
      'description': ?description,
      'color': ?color,
      'target_per_week': ?targetPerWeek,
    };
    final res = await patch('/habits/$id', body);
    notifyDataChanged();
    return res;
  }

  static Future<void> deleteHabit(int id) async {
    await delete('/habits/$id');
    notifyDataChanged();
  }

  static Future<Map<String, dynamic>> logHabit(
      int habitId, String date, bool completed) async {
    final res = await post('/habits/$habitId/logs',
        {'date': date, 'completed': completed});
    notifyDataChanged();
    return res;
  }

  static Future<void> deleteHabitLog(int habitId, String date) async {
    await delete('/habits/$habitId/logs/$date');
    notifyDataChanged();
  }

  /// Returns per-day habit activity for activity ring rendering.
  static Future<List<dynamic>> getHabitActivity({
    String? dateFrom,
    String? dateTo,
  }) async {
    final params = <String, String>{};
    if (dateFrom != null) params['date_from'] = dateFrom;
    if (dateTo != null) params['date_to'] = dateTo;
    return await get('/habits/activity', params);
  }

  // ─────────────────────────────────────
  // SUMMARY
  // ─────────────────────────────────────

  static Future<List<dynamic>> getAllSummaries() async {
    return await get('/summary');
  }

  static Future<Map<String, dynamic>> getSummary(String date) async {
    return await get('/summary/$date');
  }
}
