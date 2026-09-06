import { client } from './client';
import { User, TokenPair } from '../types';

export const login = async (email: string, password: string) => {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  const response = await client.post<TokenPair>('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return response.data;
};

export const register = async (email: string, password: string, name: string) => {
  const response = await client.post<User>('/auth/register', { email, password, name });
  return response.data;
};

export const getMe = async () => {
  const response = await client.get<User>('/users/me');
  return response.data;
};

export const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

export const googleLogin = () => {
  window.location.href = '/api/auth/google';
};
