import angular from 'angular';
import { AppComponent } from './app.component';
import { ComponentsModule } from './components.module';
import { ValidatorService } from './../services/validator.service';
import { StateService } from './../services/state.service';

import '../../styles/main.scss';
import '../../../node_modules/flexboxgrid/dist/flexboxgrid.css';
import '../../favicon.ico';

export const AppModule = angular
    .module('root', [ComponentsModule])
    .component('root', AppComponent)
    .service('ValidatorService', ValidatorService)
    .service('StateService', StateService)
    .name;

export default AppModule;
