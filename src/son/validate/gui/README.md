# son-validator-gui

A visualization tool to view all errors and warnings resulting from a validation as well as the corresponding topology and forwarding graphs.

## Getting Started

To start, clone the repository [sonata-validator-gui](https://something). Enter the repository's folder
and run `npm install` to install the needed dependencies.

### Prerequisites

To build the validator GUI a few tools are necessary:
  * Node
  * npm (included with Node)
  * Docker (Production only)

### Installing

No installation is necessary since it's a web GUI. Instead only a http server
is needed to host the static files after building it.

To build the application run the following command at the root of the repository:

```shell-session
npm run build:dev
```

Next run the `http-server` installed as a dependency

## Deployment

To deploy the application run the following set of commands

First build the docker image with:

```shell-session
docker build -t son-validate-gui .
```

Then run the image with:

```shell-session
docker run -d -p 8080:8080 -p 5050:5050 --name son-validate-gui son-validate-gui
```

To check if everything went accordingly visit [localhost:8080]()

## Built With

* [AngularJS](https://angularjs.org/) - Web framework
* [D3js](https://d3js.org/) - Document manipulation library
* [Sass](http://sass-lang.com/) - CSS extension
* [Webpack 2](https://webpack.js.org/) - Javascript module bundler

## License

The son-validator-gui is published under Apache 2.0 license. Please see the LICENSE file for more details.