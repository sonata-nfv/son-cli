import angular from 'angular';
import { GraphSelectorComponent } from './graph-selector.component';

export const GraphSelectorModule = angular.module('graphselector', [])
  .component('svGraphSelector', GraphSelectorComponent)
  .name;

export default GraphSelectorModule;
