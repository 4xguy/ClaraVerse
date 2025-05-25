// This file now acts as a compatibility layer to redirect Supabase calls to our PostgreSQL services
import { authService } from './services/auth';
import { db } from './db/pgClient';
import { storageService } from './services/storage';

// Create a compatibility layer that mimics Supabase's API
const createCompatibilityClient = () => {
  return {
    auth: {
      getSession: async () => {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          return { data: { session: null }, error: null };
        }
        
        try {
          const user = await authService.validateSession(token);
          return { 
            data: { 
              session: user ? { user, access_token: token } : null 
            }, 
            error: null 
          };
        } catch (error) {
          return { data: { session: null }, error };
        }
      },
      
      signInWithPassword: async ({ email, password }: { email: string; password: string }) => {
        try {
          const result = await authService.signIn(email, password);
          localStorage.setItem('auth_token', result.token);
          return { 
            data: { 
              user: result.user, 
              session: { user: result.user, access_token: result.token } 
            }, 
            error: null 
          };
        } catch (error) {
          return { data: null, error };
        }
      },
      
      signUp: async ({ email, password }: { email: string; password: string }) => {
        try {
          const result = await authService.signUp(email, password);
          localStorage.setItem('auth_token', result.token);
          return { 
            data: { 
              user: result.user, 
              session: { user: result.user, access_token: result.token } 
            }, 
            error: null 
          };
        } catch (error) {
          return { data: null, error };
        }
      },
      
      signOut: async () => {
        try {
          const token = localStorage.getItem('auth_token');
          if (token) {
            await authService.signOut(token);
          }
          localStorage.removeItem('auth_token');
          return { error: null };
        } catch (error) {
          return { error };
        }
      },
      
      onAuthStateChange: (callback: (event: string, session: any) => void) => {
        // Simple implementation - check token periodically
        const checkAuth = async () => {
          const token = localStorage.getItem('auth_token');
          const user = token ? await authService.validateSession(token) : null;
          callback(user ? 'SIGNED_IN' : 'SIGNED_OUT', user ? { user, access_token: token } : null);
        };
        
        // Check immediately
        checkAuth();
        
        // Check every 30 seconds
        const interval = setInterval(checkAuth, 30000);
        
        return { 
          data: { 
            subscription: { 
              unsubscribe: () => clearInterval(interval) 
            } 
          } 
        };
      }
    },
    
    from: (table: string) => ({
      select: async (columns = '*') => {
        try {
          const data = await db.query(`SELECT ${columns} FROM app.${table}`);
          return { data, error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      
      insert: async (values: any) => {
        try {
          const keys = Object.keys(values);
          const placeholders = keys.map((_, i) => `$${i + 1}`).join(', ');
          const sql = `INSERT INTO app.${table} (${keys.join(', ')}) VALUES (${placeholders}) RETURNING *`;
          const data = await db.query(sql, Object.values(values));
          return { data: data[0], error: null };
        } catch (error) {
          return { data: null, error };
        }
      },
      
      update: async (values: any) => ({
        eq: async (column: string, value: any) => {
          try {
            const keys = Object.keys(values);
            const setClause = keys.map((k, i) => `${k} = $${i + 2}`).join(', ');
            const sql = `UPDATE app.${table} SET ${setClause} WHERE ${column} = $1 RETURNING *`;
            const data = await db.query(sql, [value, ...Object.values(values)]);
            return { data: data[0], error: null };
          } catch (error) {
            return { data: null, error };
          }
        }
      }),
      
      delete: async () => ({
        eq: async (column: string, value: any) => {
          try {
            await db.query(`DELETE FROM app.${table} WHERE ${column} = $1`, [value]);
            return { data: null, error: null };
          } catch (error) {
            return { data: null, error };
          }
        }
      })
    }),
    
    storage: {
      from: (bucket: string) => ({
        upload: async (path: string, file: File | Blob, options?: any) => {
          try {
            const result = await storageService.upload(bucket, path, file, options);
            return { data: { path: result.storage_path }, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },
        
        download: async (path: string) => {
          try {
            const blob = await storageService.download(bucket, path);
            return { data: blob, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },
        
        remove: async (paths: string[]) => {
          try {
            for (const path of paths) {
              await storageService.deleteFile(bucket, path);
            }
            return { data: null, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },
        
        list: async (path?: string, options?: any) => {
          try {
            const files = await storageService.listFiles(bucket, { 
              prefix: path, 
              ...options 
            });
            return { data: files, error: null };
          } catch (error) {
            return { data: null, error };
          }
        },
        
        getPublicUrl: (path: string) => ({
          data: { publicUrl: storageService.getPublicUrl(bucket, path) }
        })
      })
    }
  };
};

// Export the compatibility client
export const supabase = createCompatibilityClient();

// Admin client is no longer needed
export const supabaseAdmin = null;
