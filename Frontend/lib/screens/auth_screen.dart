import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../auth_state.dart';

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

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await widget.authState
        .login(_userCtrl.text.trim(), _passCtrl.text);
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(widget.authState.error ?? 'Login failed'),
          backgroundColor: Colors.red.shade700));
    }
  }

  Future<void> _adminLogin() async {
    final ok = await widget.authState.adminLogin();
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(widget.authState.error ?? 'Admin login failed'),
          backgroundColor: Colors.red.shade700));
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
                  Text('MyFit',
                      style: TextStyle(
                          fontSize: 32,
                          fontWeight: FontWeight.w700,
                          color: Theme.of(context).colorScheme.primary)),
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
  final _weightCtrl = TextEditingController();
  final _heightCtrl = TextEditingController();
  bool _obscure = true;
  DateTime _birthdate = DateTime(1995, 1, 1);

  @override
  void dispose() {
    _userCtrl.dispose();
    _passCtrl.dispose();
    _weightCtrl.dispose();
    _heightCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final ok = await widget.authState.register(
      username: _userCtrl.text.trim(),
      password: _passCtrl.text,
      weight: double.parse(_weightCtrl.text),
      height: double.parse(_heightCtrl.text),
      birthdate:
          '${_birthdate.year}-${_birthdate.month.toString().padLeft(2, '0')}-${_birthdate.day.toString().padLeft(2, '0')}',
    );
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(widget.authState.error ?? 'Registration failed'),
          backgroundColor: Colors.red.shade700));
    }
  }

  Future<void> _pickDate() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _birthdate,
      firstDate: DateTime(1920),
      lastDate: DateTime.now().subtract(const Duration(days: 365 * 10)),
    );
    if (d != null) setState(() => _birthdate = d);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Create Account'),
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
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _weightCtrl,
                            decoration:
                                const InputDecoration(labelText: 'Weight (kg)'),
                            keyboardType: TextInputType.number,
                            inputFormatters: [
                              FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
                            ],
                            validator: (v) {
                              final n = double.tryParse(v ?? '');
                              return n == null || n <= 0 ? 'Enter weight' : null;
                            },
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _heightCtrl,
                            decoration:
                                const InputDecoration(labelText: 'Height (cm)'),
                            keyboardType: TextInputType.number,
                            inputFormatters: [
                              FilteringTextInputFormatter.allow(RegExp(r'[\d.]'))
                            ],
                            validator: (v) {
                              final n = double.tryParse(v ?? '');
                              return n == null || n <= 0 ? 'Enter height' : null;
                            },
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: _pickDate,
                      icon: const Icon(Icons.calendar_today, size: 16),
                      label: Text(
                          'Birthdate: ${_birthdate.year}-${_birthdate.month.toString().padLeft(2, '0')}-${_birthdate.day.toString().padLeft(2, '0')}'),
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
