import { createClient } from '@supabase/supabase-js';

// Get Supabase URL and keys from environment variables
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://qtnaotlbkjfqhzwsnqxc.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'dummy-key-for-deployment';

// Create a dummy client for deployment without actual Supabase
// This allows the app to run without crashing
let supabaseClient;
try {
  if (supabaseAnonKey === 'dummy-key-for-deployment') {
    console.warn('Running without Supabase - some features may be limited');
    // Create a mock client that won't crash
    supabaseClient = {
      auth: {
        getSession: async () => ({ data: { session: null }, error: null }),
        signIn: async () => ({ data: null, error: new Error('Supabase not configured') }),
        signOut: async () => ({ error: null }),
        onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
      },
      from: () => ({
        select: async () => ({ data: [], error: null }),
        insert: async () => ({ data: null, error: new Error('Supabase not configured') }),
        update: async () => ({ data: null, error: new Error('Supabase not configured') }),
        delete: async () => ({ data: null, error: new Error('Supabase not configured') })
      })
    };
  } else {
    supabaseClient = createClient(supabaseUrl, supabaseAnonKey);
  }
} catch (error) {
  console.error('Failed to initialize Supabase:', error);
  // Provide a fallback mock client
  supabaseClient = {
    auth: {
      getSession: async () => ({ data: { session: null }, error: null }),
      signIn: async () => ({ data: null, error: new Error('Supabase not configured') }),
      signOut: async () => ({ error: null }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
    },
    from: () => ({
      select: async () => ({ data: [], error: null }),
      insert: async () => ({ data: null, error: new Error('Supabase not configured') }),
      update: async () => ({ data: null, error: new Error('Supabase not configured') }),
      delete: async () => ({ data: null, error: new Error('Supabase not configured') })
    })
  };
}

export const supabase = supabaseClient;

// Admin client with service key (for admin operations only)
// This should ONLY be used in secure server environments, never in client-side code
const supabaseServiceKey = import.meta.env.VITE_SUPABASE_SERVICE_KEY || '';
export const supabaseAdmin = null; // Disabled for web deployment
