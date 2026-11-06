import 'package:flutter/material.dart';
import '../auth_state.dart';
import '../widgets/server_settings_dialog.dart';

// ─────────────────────────────────────────
// LOGIN SCREEN
// ─────────────────────────────────────────

class LoginScreen extends StatefulWidget {
  final AuthState authState;
  const LoginScreen({super.key, required this.authState});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  void _showErrorSnackBar(String err) {
    if (!mounted) return;
    final isConnErr = err.toLowerCase().contains('connection') ||
        err.toLowerCase().contains('socket') ||
        err.toLowerCase().contains('failed');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(err),
        backgroundColor: Colors.red.shade700,
        action: isConnErr
            ? SnackBarAction(
                label: 'Settings',
                textColor: Colors.white,
                onPressed: () => showServerSettingsDialog(context),
              )
            : null,
      ),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await widget.authState
        .login(_userCtrl.text.trim(), _passCtrl.text);
    if (!ok && mounted) {
      _showErrorSnackBar(widget.authState.error ?? 'Login failed');
    }
  }

  Future<void> _adminLogin() async {
    final ok = await widget.authState.adminLogin();
    if (!ok && mounted) {
      _showErrorSnackBar(widget.authState.error ?? 'Admin login failed');
    }
  }

  void _navigateToRegister() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => RegisterScreen(authState: widget.authState),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Text('MyFit',
                          style: TextStyle(
                              fontSize: 32,
                              fontWeight: FontWeight.w700,
                              color: Theme.of(context).colorScheme.primary)),
                      IconButton(
                        icon: const Icon(Icons.dns_outlined),
                        tooltip: 'Server Settings',
                        onPressed: () => showServerSettingsDialog(context),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  const Text('Track food, exercise & habits.',
                      style: TextStyle(color: Color(0xFF6B7280), fontSize: 15)),
                  const SizedBox(height: 36),
                  Form(
                    key: _formKey,
                    child: Column(
                      children: [
                        TextFormField(
                          controller: _userCtrl,
                          decoration:
                              const InputDecoration(labelText: 'Username'),
                          validator: (v) =>
                              v == null || v.trim().isEmpty ? 'Required' : null,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _passCtrl,
                          obscureText: _obscure,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            suffixIcon: IconButton(
                              icon: Icon(_obscure
                                  ? Icons.visibility_off
                                  : Icons.visibility),
                              onPressed: () =>
                                  setState(() => _obscure = !_obscure),
                            ),
                          ),
                          validator: (v) =>
                              v == null || v.isEmpty ? 'Required' : null,
                        ),
                        const SizedBox(height: 24),
                        ListenableBuilder(
                          listenable: widget.authState,
                          builder: (context2, child2) => FilledButton(
                            onPressed: widget.authState.loading ? null : _submit,
                            child: widget.authState.loading
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white))
                                : const Text('Sign In'),
                          ),
                        ),
                        const SizedBox(height: 12),
                        ListenableBuilder(
                          listenable: widget.authState,
                          builder: (context2, child2) => SizedBox(
                            width: double.infinity,
                            child: OutlinedButton.icon(
                              icon: const Icon(Icons.admin_panel_settings_outlined, size: 18),
                              label: const Text('Admin'),
                              onPressed: widget.authState.loading
                                  ? null
                                  : _adminLogin,
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextButton(
                          onPressed: _navigateToRegister,
                          child: const Text("Don't have an account? Register"),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// REGISTER SCREEN (Dedicated Page)
// ─────────────────────────────────────────

class RegisterScreen extends StatefulWidget {
  final AuthState authState;
  const RegisterScreen({super.key, required this.authState});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _confirmPassCtrl = TextEditingController();
  bool _obscure = true;
  bool _obscureConfirm = true;

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    _confirmPassCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await widget.authState.register(
      username: _userCtrl.text.trim(),
      password: _passCtrl.text,
    );
    if (!ok && mounted) {
      final err = widget.authState.error ?? 'Registration failed';
      final isConnErr = err.toLowerCase().contains('connection') ||
          err.toLowerCase().contains('socket') ||
          err.toLowerCase().contains('failed');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(err),
        backgroundColor: Colors.red.shade700,
        action: isConnErr
            ? SnackBarAction(
                label: 'Settings',
                textColor: Colors.white,
                onPressed: () => showServerSettingsDialog(context),
              )
            : null,
      ));
    } else if (ok && mounted) {
      // Return back to root where authState listenable will display onboarding GoalScreen
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Account'),
        actions: [
          IconButton(
            icon: const Icon(Icons.dns_outlined),
            tooltip: 'Server Settings',
            onPressed: () => showServerSettingsDialog(context),
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextFormField(
                      controller: _userCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Username',
                        hintText: 'e.g. johndoe',
                      ),
                      validator: (v) =>
                          v == null || v.trim().length < 3 ? 'Min 3 characters' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _passCtrl,
                      obscureText: _obscure,
                      decoration: InputDecoration(
                        labelText: 'Password',
                        suffixIcon: IconButton(
                          icon: Icon(_obscure
                              ? Icons.visibility_off
                              : Icons.visibility),
                          onPressed: () =>
                              setState(() => _obscure = !_obscure),
                        ),
                      ),
                      validator: (v) =>
                          v == null || v.length < 8 ? 'Min 8 characters' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _confirmPassCtrl,
                      obscureText: _obscureConfirm,
                      decoration: InputDecoration(
                        labelText: 'Confirm Password',
                        suffixIcon: IconButton(
                          icon: Icon(_obscureConfirm
                              ? Icons.visibility_off
                              : Icons.visibility),
                          onPressed: () =>
                              setState(() => _obscureConfirm = !_obscureConfirm),
                        ),
                      ),
                      validator: (v) {
                        if (v == null || v.isEmpty) {
                          return 'Please confirm your password';
                        }
                        if (v != _passCtrl.text) {
                          return 'Passwords do not match';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 24),
                    ListenableBuilder(
                      listenable: widget.authState,
                      builder: (context2, child2) => FilledButton(
                        onPressed: widget.authState.loading ? null : _submit,
                        child: widget.authState.loading
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white))
                            : const Text('Create Account'),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Already have an account? Sign In'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
