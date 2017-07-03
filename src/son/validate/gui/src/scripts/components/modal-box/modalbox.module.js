import angular from 'angular';
import { ModalBoxComponent } from './modalbox.component';

export const ModalBoxModule = angular.module('modalbox', [])
    .component('svModalBox', ModalBoxComponent)
    .name;
