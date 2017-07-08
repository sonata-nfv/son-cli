const webpack = require('webpack');
const path = require('path');
const Merge = require('webpack-merge');
const CommonConfig = require('./webpack.common.js');

module.exports = Merge(CommonConfig, {
  output: {
    filename: '[name].bundle.js',
    path: path.join(__dirname, 'dist'),
  },
  plugins: [
    new webpack.optimize.UglifyJsPlugin({
      beautify: false,
      compress: {
        unused: true,
        dead_code: true,
        drop_console: true,
      },
      mangle: true,
      comments: false,
    }),
  ],
});
