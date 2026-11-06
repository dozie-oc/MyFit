import 'package:flutter/material.dart';
import '../services/api_client.dart';

Future<bool?> showServerSettingsDialog(BuildContext context) {
  return showDialog<bool>(
    context: context,
    builder: (context) => const ServerSettingsDialog(),
  );
}

class ServerSettingsDialog extends StatefulWidget {
  const ServerSettingsDialog({super.key});

  @override
  State<ServerSettingsDialog> createState() => _ServerSettingsDialogState();
}

class _ServerSettingsDialogState extends State<ServerSettingsDialog> {
  late final TextEditingController _urlCtrl;
  bool _testing = false;
  ({bool ok, String message})? _testResult;

  @override
  void initState() {
    super.initState();
    _urlCtrl = TextEditingController(text: ApiClient.getBaseUrl());
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  Future<void> _testConnection() async {
    setState(() {
      _testing = true;
      _testResult = null;
    });
    final res = await ApiClient.testConnection(_urlCtrl.text);
    if (mounted) {
      setState(() {
        _testing = false;
        _testResult = res;
      });
    }
  }

  Future<void> _save() async {
    final newUrl = _urlCtrl.text.trim();
    await ApiClient.setCustomBaseUrl(newUrl);
    if (mounted) {
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Server URL set to ${ApiClient.getBaseUrl()}'),
          backgroundColor: const Color(0xFF059669),
        ),
      );
    }
  }

  void _reset() {
    final def = ApiClient.getDefaultBaseUrl();
    setState(() {
      _urlCtrl.text = def;
      _testResult = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.dns_outlined, size: 24),
          SizedBox(width: 8),
          Text(
            'Server Settings',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 400),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Enter the backend server URL. When testing on a physical phone, use your PC\'s local Wi-Fi IP address.',
                style: TextStyle(fontSize: 13, color: Color(0xFF6B7280)),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _urlCtrl,
                keyboardType: TextInputType.url,
                autocorrect: false,
                decoration: InputDecoration(
                  labelText: 'Server Base URL',
                  hintText: 'http://10.11.91.7:8000',
                  suffixIcon: IconButton(
                    icon: const Icon(Icons.clear, size: 18),
                    onPressed: () => _urlCtrl.clear(),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _testing ? null : _testConnection,
                icon: _testing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.network_check, size: 18),
                label: Text(_testing ? 'Testing...' : 'Test Connection'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(38),
                ),
              ),
              if (_testResult != null) ...[
                const SizedBox(height: 10),
                Container(
                  width: double.infinity,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: _testResult!.ok
                        ? const Color(0xFFECFDF5)
                        : const Color(0xFFFEF2F2),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                      color: _testResult!.ok
                          ? const Color(0xFF10B981)
                          : const Color(0xFFEF4444),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _testResult!.ok
                            ? Icons.check_circle
                            : Icons.error_outline,
                        color: _testResult!.ok
                            ? const Color(0xFF059669)
                            : const Color(0xFFDC2626),
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _testResult!.message,
                          style: TextStyle(
                            fontSize: 12,
                            color: _testResult!.ok
                                ? const Color(0xFF065F46)
                                : const Color(0xFF991B1B),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: _reset,
                  child: const Text('Reset to Default',
                      style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          child: const Text('Save'),
        ),
      ],
    );
  }
}

