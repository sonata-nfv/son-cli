import angular from 'angular';
import { ModalBoxComponent } from './modalbox.component';
import { FileOnChange } from './fileonchange.directive';

export const ModalBoxModule = angular.module('modalbox', [])
    .component('svModalBox', ModalBoxComponent)
    .directive('svFileUpload', FileOnChange)
    .name;

export default ModalBoxModule;

