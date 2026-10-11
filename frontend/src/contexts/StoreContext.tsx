'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { Store } from '@/types';
import { api } from '@/lib/api';
import { useAuth } from './AuthContext';

interface StoreContextType {
  stores: Store[];
  activeStore: Store | null;
  loading: boolean;
  switchStore: (storeId: string) => void;
  refreshStores: () => Promise<void>;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [stores, setStores] = useState<Store[]>([]);
  const [activeStore, setActiveStore] = useState<Store | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchStores = async () => {
    if (!user) {
      setStores([]);
      setActiveStore(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await api.getStores();
      const list: Store[] = Array.isArray(data) ? data : data.results || [];
      setStores(list);

      const savedStoreId = localStorage.getItem('shoppilot_active_store_id');
      const found = list.find((s) => s.id === savedStoreId);
      if (found) {
        setActiveStore(found);
      } else if (list.length > 0) {
        setActiveStore(list[0]);
        localStorage.setItem('shoppilot_active_store_id', list[0].id);
      } else {
        setActiveStore(null);
      }
    } catch (err) {
      console.warn('Failed to fetch stores', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStores();
  }, [user]);

  const switchStore = (storeId: string) => {
    const s = stores.find((item) => item.id === storeId);
    if (s) {
      setActiveStore(s);
      localStorage.setItem('shoppilot_active_store_id', s.id);
      window.location.reload(); // Reload to refresh all store-scoped views
    }
  };

  return (
    <StoreContext.Provider value={{ stores, activeStore, loading, switchStore, refreshStores: fetchStores }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error('useStore must be used within a StoreProvider');
  }
  return context;
}
