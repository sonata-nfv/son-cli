import angular from 'angular';
import { ControlMenuComponent } from './controlmenu.component';

export const ControlMenuModule = angular.module('controlmenu', [])
    .component('svControlMenu', ControlMenuComponent)
    .name;

export default ControlMenuModule;
