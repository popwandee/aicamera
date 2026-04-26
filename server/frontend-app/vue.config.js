const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  // Serve under /server/ for nginx; assets will load as /server/js/..., /server/css/...
  publicPath: process.env.NODE_ENV === 'production' ? '/server/' : '/'
})
