import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import * as authApi from "../api/auth";
import { User } from "../types";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, name: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  handleOAuthCallback: (
    accessToken: string,
    refreshToken: string,
  ) => Promise<User>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const u = await authApi.getMe();
          setUser(u);
        } catch (error) {
          console.error("Failed to authenticate on load", error);
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email: string, pass: string) => {
    const tokens = await authApi.login(email, pass);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const u = await authApi.getMe();
    setUser(u);
  };

  const register = async (email: string, pass: string, name: string) => {
    const tokens = await authApi.register(email, pass, name);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const u = await authApi.getMe();
    setUser(u);
  };

  const handleOAuthCallback = async (
    accessToken: string,
    refreshToken: string,
  ) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    const u = await authApi.getMe();
    setUser(u);
    return u;
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
  };

  const refreshToken = async () => {
    // Already handled by interceptor ideally, but can be forced
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshToken,
        handleOAuthCallback,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
