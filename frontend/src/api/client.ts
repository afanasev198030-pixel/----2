import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

// Use same origin - go through nginx proxy on port 80
// nginx routes /api/v1/ to core-api, /api/v1/files/ to file-service
const API_BASE = window.location.port === '3000'
  ? `${window.location.protocol}//${window.location.hostname}:80/api/v1`
  : '/api/v1';

const client: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
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