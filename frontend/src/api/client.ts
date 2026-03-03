import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

// API base URL: use proxy (CRA proxy or nginx)
// In dev mode (port 3000), CRA proxies /api/v1/ to core-api
const API_BASE = '/api/v1';

const client: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token + X-Request-ID
client.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.headers && !config.headers['X-Request-ID']) {
      config.headers['X-Request-ID'] = crypto.randomUUID();
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default client;
// force rebuild