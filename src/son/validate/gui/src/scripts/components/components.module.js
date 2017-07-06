import angular from 'angular';
import { ViewerModule } from './viewer/viewer.module';
import { ControlMenuModule } from './control-menu/controlmenu.module';
import { ModalBoxModule } from './modal-box/modalbox.module';
import { GraphSelectorModule } from './graph-selector/graph-selector.module';
import { ResultsViewerModule } from './results-viewer/results-viewer.module';

export const ComponentsModule = angular.module('root.components', [
  ViewerModule,
  ControlMenuModule,
  ModalBoxModule,
  GraphSelectorModule,
  ResultsViewerModule,
])
  .name;

export default ComponentsModule;
