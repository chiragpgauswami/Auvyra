import axios from "axios";
import { TokenPair } from "../types";

export const client = axios.create({
  baseURL: "/api",
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem("refresh_token");
        const res = await client.post<TokenPair>("/auth/refresh", {
          refresh_token: refreshToken,
        });
        localStorage.setItem("access_token", res.data.access_token);
        localStorage.setItem("refresh_token", res.data.refresh_token);
        return client(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  },
);

export default client;
