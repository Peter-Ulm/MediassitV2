import { useEffect, useState } from 'react';
import { api } from '../api';
import type { AdminUser } from '../api/types';
import { useAuth } from '../features/auth/auth-context';

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const [usersList, setUsersList] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ email: '', name: '', password: '', role: 'clinician' as 'clinician' | 'admin' });

  const load = async () => {
    try { setUsersList(await api.listUsers()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to load users'); }
  };
  useEffect(() => { load(); }, []);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await api.createUser(form);
      setForm({ email: '', name: '', password: '', role: 'clinician' });
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Create failed'); }
  };

  const toggleActive = async (u: AdminUser) => {
    setError('');
    try { await api.updateUser(u.id, { isActive: !u.isActive }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed'); }
  };

  const changeRole = async (u: AdminUser, role: 'clinician' | 'admin') => {
    setError('');
    try { await api.updateUser(u.id, { role }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed'); }
  };

  const resetPassword = async (u: AdminUser) => {
    const pw = window.prompt(`New password for ${u.email}:`);
    if (!pw) return;
    setError('');
    try { await api.resetUserPassword(u.id, pw); alert('Password reset.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Reset failed'); }
  };

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-bold text-slate-900">User management</h1>
      <p className="mt-1 text-sm text-slate-500">Create and manage clinician and admin accounts.</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={onCreate} className="mt-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-5">
        <input required type="email" placeholder="email" value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input required placeholder="name" value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input required type="password" placeholder="password" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as 'clinician' | 'admin' })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="clinician">clinician</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-bold text-white hover:bg-teal-800">
          Create user
        </button>
      </form>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {usersList.map((u) => {
              const isSelf = u.id === me?.id;
              return (
                <tr key={u.id}>
                  <td className="px-4 py-3"><div className="font-semibold text-slate-900">{u.name}</div><div className="text-xs text-slate-500">{u.email}</div></td>
                  <td className="px-4 py-3">
                    <select value={u.role} disabled={isSelf}
                      onChange={(e) => changeRole(u, e.target.value as 'clinician' | 'admin')}
                      className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                      <option value="clinician">clinician</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${u.isActive ? 'bg-teal-50 text-teal-800' : 'bg-slate-100 text-slate-500'}`}>
                      {u.isActive ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => resetPassword(u)} className="mr-2 rounded border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">Reset password</button>
                    <button onClick={() => toggleActive(u)} disabled={isSelf}
                      className="rounded border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                      {u.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
