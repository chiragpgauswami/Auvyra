import { TokenPair, User } from "../types";
import { client } from "./client";

export const login = async (email: string, password: string) => {
  const response = await client.post<TokenPair>("/auth/login", {
    email,
    password,
  });
  return response.data;
};

export const register = async (
  email: string,
  password: string,
  name: string,
) => {
  const response = await client.post<TokenPair>("/auth/register", {
    email,
    password,
    name,
  });
  return response.data;
};

export const getMe = async () => {
  const response = await client.get<User>("/auth/me");
  return response.data;
};

export const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
};

export const googleLogin = () => {
  window.location.href = "/api/auth/google";
};
