import template from './viewer.html';
import { LOADING_EVENT, GRAPH_EVENT } from '../../services/event-strings';

import '../../../assets/img/loading-crop.gif';

export const ViewerComponent = {

  template,
  bindings: {
    topology: '<',
    fwgraphs: '<',
    errors: '<',
    warnings: '<',
  },
  controller: class ViewerComponent {
    constructor($scope, ValidatorService) {
      'ngInject';

      this.scope = $scope;
      this.validatorService = ValidatorService;
      this.project = {
        name: '',
      };
      this.searchTerm = '';
      this.isLoading = false;
      this.scope.isValid = false;
    }

    $onInit() {
      this.scope.$on(LOADING_EVENT, (event, data) => {
        this.isLoading = data.isLoading;
        this.scope.isInvalid = data.isInvalid;
        this.scope.message = data.message;
      });

      this.scope.$on(GRAPH_EVENT.CAST, (event, data) => {
        if (this.scope.fwgraph.id !== data.id) {
          const found = this.fwgraphs.find(fwg => fwg.id === data.id);
          if (found) {
            found.isActive = data.visible;
            this.scope.fwgraph = found;
          }
        } else {
          this.scope.fwgraph.isActive = data.visible;
        }
      });
    }

    $onChanges(changesObj) {
      if (changesObj.errors) {
        this.tmperrors = changesObj.errors.currentValue;
      }

      if (changesObj.warnings) {
        this.tmpwarnings = changesObj.warnings.currentValue;
      }
      if (changesObj.topology && changesObj.topology.currentValue) {
        this.isLoading = false;
        this.scope.topology = changesObj.topology.currentValue;
        this.scope.errors = this.tmperrors;
        this.scope.warnings = this.tmpwarnings;
        this.scope.isValid = true;
      } else if (changesObj.topology) {
        if (changesObj.topology.currentValue === null) {
          this.clearData();
        }
      }

      if (changesObj.fwgraphs && changesObj.fwgraphs.currentValue) {
        this.fwgraphs = changesObj.fwgraphs.currentValue;
        this.scope.fwgraph = this.fwgraphs[0];
      }
    }

    clearData() {
      this.scope.topology = null;
      this.fwgraphs.length = 0;
      this.scope.fwgraph = null;
    }
  },
};

export default ViewerComponent;

