import React, { useEffect, useState } from 'react';
import {
  User,
  Shield,
  Cpu,
  Palette,
  Sun,
  Moon,
  Save,
  CheckCircle,
  AlertCircle,
  Brain,
  Key,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { authApi } from '../api/auth';
import { systemApi } from '../api/system';

export const Settings = () => {
  const { user, setUser } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [provider, setProvider] = useState('local');
  const [geminiKey, setGeminiKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [modelsInfo, setModelsInfo] = useState(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '');
      setProvider(user.preferences?.default_provider || 'local');
    }
    const fetchSystem = async () => {
      try {
        const info = await systemApi.getModels();
        setModelsInfo(info);
      } catch (e) {
        console.error(e);
      }
    };
    fetchSystem();
  }, [user]);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      const updated = await authApi.updateProfile({
        full_name: fullName,
        preferences: {
          ...user?.preferences,
          default_provider: provider,
        },
      });
      setUser(updated);
      setMessage('Profile and preferences updated successfully.');
    } catch (err) {
      setMessage('Error updating profile: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setMessage('Password changed successfully.');
    } catch (err) {
      setMessage('Failed to change password: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Platform Settings & Model Configuration
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account profile, theme preferences, local hardware acceleration, and AI provider integrations.
        </p>
      </div>

      {message && (
        <div className="flex items-center gap-3 rounded-xl bg-primary-50 dark:bg-primary-950/40 border border-primary-200 dark:border-primary-900 p-3.5 text-xs text-primary-800 dark:text-primary-300">
          <CheckCircle className="h-4 w-4 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* User Profile Card */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-surface-darkBorder">
          <User className="h-4 w-4 text-primary-600" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Profile Information
          </h2>
        </div>

        <form onSubmit={handleSaveProfile} className="space-y-4 max-w-md">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-primary-600"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <input
              type="email"
              disabled
              value={user?.email || ''}
              className="w-full rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-slate-100 dark:bg-slate-800/50 px-3 py-2 text-sm text-slate-500 cursor-not-allowed"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            <span>Save Profile</span>
          </button>
        </form>
      </div>

      {/* LLM Provider Configuration with Authoritative Privacy Notice */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-5">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-surface-darkBorder">
          <Brain className="h-4 w-4 text-primary-600" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            LLM Generation Provider
          </h2>
        </div>

        {/* Privacy Notice Box */}
        <div className="rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 p-4 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
          <Shield className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
          <div>
            <span className="font-bold">Strict Privacy Notice: </span>
            <span>
              By default, all document parsing, embeddings, extractive algorithms, and question generation run 100% locally on your machine. Documents and chunks are NEVER sent to external cloud APIs unless you explicitly configure and select an external provider below.
            </span>
          </div>
        </div>

        <div className="space-y-4 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Active Provider
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'local', label: 'Local (FLAN-T5)' },
                { id: 'gemini', label: 'Google Gemini' },
                { id: 'openai', label: 'OpenAI GPT' },
              ].map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setProvider(p.id)}
                  className={`rounded-xl py-2.5 px-3 text-xs font-bold border transition-all ${
                    provider === p.id
                      ? 'border-primary-600 bg-primary-50 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300 shadow-xs'
                      : 'border-slate-200 dark:border-surface-darkBorder text-slate-600 dark:text-slate-400 hover:bg-slate-50'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {provider === 'gemini' && (
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Gemini API Key
              </label>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-xs text-slate-900 dark:text-white"
              />
            </div>
          )}

          {provider === 'openai' && (
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                OpenAI API Key
              </label>
              <input
                type="password"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-xs text-slate-900 dark:text-white"
              />
            </div>
          )}
        </div>
      </div>

      {/* Hardware & Model Resident Status */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-surface-darkBorder">
          <Cpu className="h-4 w-4 text-primary-600" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Local Hardware & Model Manager
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-3 border border-slate-200/50 dark:border-surface-darkBorder">
            <span className="text-slate-400 uppercase font-semibold">Compute Device</span>
            <p className="text-sm font-bold text-slate-900 dark:text-white mt-1">
              {modelsInfo?.device || 'CPU (Standard)'}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-3 border border-slate-200/50 dark:border-surface-darkBorder">
            <span className="text-slate-400 uppercase font-semibold">Resident Heavy Model</span>
            <p className="text-sm font-bold text-slate-900 dark:text-white mt-1">
              {modelsInfo?.active_model || 'None (Lazy Unloaded)'}
            </p>
          </div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-3 border border-slate-200/50 dark:border-surface-darkBorder">
            <span className="text-slate-400 uppercase font-semibold">Memory Policy</span>
            <p className="text-sm font-bold text-emerald-600 mt-1">
              Single Resident / VRAM Safe
            </p>
          </div>
        </div>
      </div>

      {/* Theme & Display Mode */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-surface-darkBorder">
          <Palette className="h-4 w-4 text-primary-600" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Appearance
          </h2>
        </div>

        <div className="flex items-center justify-between max-w-sm">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">Interface Theme</p>
            <p className="text-xs text-slate-400">Current mode: {theme === 'dark' ? 'Dark' : 'Light'}</p>
          </div>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4 text-amber-500" /> : <Moon className="h-4 w-4 text-slate-600" />}
            <span>Toggle {theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
