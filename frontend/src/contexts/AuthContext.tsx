'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '@/types';
import { api } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: { email?: string; phone_number?: string; password: string }) => Promise<void>;
  register: (data: { email?: string; phone_number?: string; full_name: string; password: string; business_name?: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadUser() {
      const token = localStorage.getItem('shoppilot_access_token');
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const u = await api.getMe();
        setUser(u);
      } catch (err) {
        console.warn('Failed to load user session', err);
        localStorage.removeItem('shoppilot_access_token');
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, []);

  const login = async (credentials: { email?: string; phone_number?: string; password: string }) => {
    const res = await api.login(credentials);
    localStorage.setItem('shoppilot_access_token', res.access);
    localStorage.setItem('shoppilot_refresh_token', res.refresh);
    setUser(res.user);
  };

  const register = async (data: { email?: string; phone_number?: string; full_name: string; password: string; business_name?: string }) => {
    const res = await api.register(data);
    localStorage.setItem('shoppilot_access_token', res.access);
    localStorage.setItem('shoppilot_refresh_token', res.refresh);
    setUser(res.user);
  };

  const logout = () => {
    localStorage.removeItem('shoppilot_access_token');
    localStorage.removeItem('shoppilot_refresh_token');
    localStorage.removeItem('shoppilot_active_store_id');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
