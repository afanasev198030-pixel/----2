const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {

  // AI service: keep full path /api/v1/ai/*
  app.use(createProxyMiddleware({
    target: 'http://ai-service:8003',
    changeOrigin: true,
    pathFilter: '/api/v1/ai/**',
    logger: console,
    timeout: 600000,
    proxyTimeout: 600000,
  }));

  // Integration service: keep full path /api/v1/integration/*
  app.use(createProxyMiddleware({
    target: 'http://integration-service:8004',
    changeOrigin: true,
    pathFilter: '/api/v1/integration/**',
    logger: console,
  }));

  // Calc service: keep full path /api/v1/calc/*
  app.use(createProxyMiddleware({
    target: 'http://calc-service:8005',
    changeOrigin: true,
    pathFilter: '/api/v1/calc/**',
    logger: console,
  }));

  // File service: keep full path /api/v1/files/*
  app.use(createProxyMiddleware({
    target: 'http://file-service:8002',
    changeOrigin: true,
    pathFilter: '/api/v1/files/**',
    logger: console,
  }));

  // Core API: keep full path /api/v1/*
  app.use(createProxyMiddleware({
    target: 'http://core-api:8001',
    changeOrigin: true,
    pathFilter: '/api/v1/**',
    logger: console,
  }));
};
