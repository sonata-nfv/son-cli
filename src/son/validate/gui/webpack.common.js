const webpack = require('webpack');
const path = require('path');
const ExtractTextPlugin = require('extract-text-webpack-plugin');
const NgAnnotatePlugin = require('ng-annotate-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');

module.exports = {
  entry: {
    app: path.resolve(__dirname, 'src', 'scripts', 'components', 'app.module.js'),
    vendor: ['angular'],
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: [
              'es2015',
              ['es2015', { 'modules': false }],
            ],
            plugins: ['transform-exponentiation-operator'],
          },
        },
      },
      {
        test: /\.html$/,
        use: {
          loader: 'html-loader',
        },
      },
      {
        test: /\.(eot|svg|ttf|woff|woff2)$/,
        include: path.resolve(__dirname, 'src', 'assets', 'fonts'),
        use: {
          loader: 'file-loader?name=fonts/[name].[ext]',
        },
      },
      {
        test: /\.scss$/,
        use: ExtractTextPlugin.extract({
          fallback: 'style-loader',
          use: [
            { loader: 'css-loader' },
            { loader: 'sass-loader' },
          ],
        }),
      },
      {
        test: /\.css$/,
        use: ExtractTextPlugin.extract({
          fallback: 'style-loader',
          use: [
            { loader: 'css-loader' },
          ],
        }),
      },
      {
        test: /\.png$/,
        include: path.resolve(__dirname, 'src', 'assets', 'img'),
        use: {
          loader: 'file-loader?name=images/[name].[ext]',
        },
      },
      {
        test: /\.svg$/,
        include: path.resolve(__dirname, 'src', 'assets', 'icons'),
        use: {
          loader: 'file-loader?name=icons/[name].[ext]',
        },
      },
      {
        test: /\.gif$/,
        include: path.resolve(__dirname, 'src', 'assets', 'img'),
        use: {
          loader: 'file-loader?name=images/[name].[ext]',
        },
      },
      {
        test: /\.ico$/,
        include: path.resolve(__dirname, 'src'),
        use: {
          loader: 'file-loader?name=[name].[ext]',
        },
      },
    ],
  },
  plugins: [
    new ExtractTextPlugin('[name].css'),
    new HtmlWebpackPlugin({ template: 'index.html', chunksSortMode: 'dependency' }),
    new webpack.HotModuleReplacementPlugin(),
    new NgAnnotatePlugin({ add: true }),
    new webpack.optimize.CommonsChunkPlugin({
      name: 'vendor', 
      filename: 'vendor.bundle.js',
    }),
  ],
  devServer: {
    port: 8081,
    hot: true,
    contentBase: path.join(__dirname, 'dist'),
  },
};
