import angular from 'angular';
import { ViewerComponent } from './viewer.component';
import { ViewerDirective } from './viewer.directive';

export const ViewerModule = angular.module('viewer', [])
    .component('svViewer', ViewerComponent)
    .directive('viewerSvg', ViewerDirective)
    .name;

export default ViewerModule;
