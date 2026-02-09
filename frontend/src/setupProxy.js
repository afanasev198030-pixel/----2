const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // AI service: keep full path /api/v1/ai/*
  app.use(createProxyMiddleware({
    target: 'http://127.0.0.1:8003',
    changeOrigin: true,
    pathFilter: '/api/v1/ai/**',
    logger: console,
  }));

  // Calc service: keep full path /api/v1/calc/*
  app.use(createProxyMiddleware({
    target: 'http://127.0.0.1:8005',
    changeOrigin: true,
    pathFilter: '/api/v1/calc/**',
    logger: console,
  }));

  // File service: keep full path /api/v1/files/*
  app.use(createProxyMiddleware({
    target: 'http://127.0.0.1:8002',
    changeOrigin: true,
    pathFilter: '/api/v1/files/**',
    logger: console,
  }));

  // Core API: keep full path /api/v1/*
  app.use(createProxyMiddleware({
    target: 'http://127.0.0.1:8001',
    changeOrigin: true,
    pathFilter: '/api/v1/**',
    logger: console,
  }));
};
