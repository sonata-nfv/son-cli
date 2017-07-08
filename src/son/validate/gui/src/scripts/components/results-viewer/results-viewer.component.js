import template from './results-viewer.html';
import { HIGHLIGHT_EVENT } from '../../services/event-strings';

const minWidth = 1500;

export const ResultsViewerComponent = {
  template,
  bindings: {
    fwgraphs: '<',
    errors: '<',
    warnings: '<',
  },
  controller: class ResultsViewerComponent {
    constructor($scope, $window) {
      'ngInject';

      this.scope = $scope;
      this.window = $window;
      this.scope.isOpen = false;
      this.collapseErrors = true;
      this.collapseWarns = true;
    }

    $postLink() {
      this.scope.isOpen = this.window.innerWidth > minWidth;
    }

    $onChanges(changesObj) {
      if (changesObj.errors && changesObj.errors.currentValue) {
        this.errors = [...changesObj.errors.currentValue];
      }

      if (changesObj.warnings && changesObj.warnings.currentValue) {
        this.warnings = [...changesObj.warnings.currentValue];
      }
    }

    searchTopology(search) {
      this.scope.$emit(HIGHLIGHT_EVENT.EMIT,
        {
          search: true,
          hlight: true,
          id: search,
        });
    }

    toggleDrawer() {
      this.scope.isOpen = !this.scope.isOpen;
    }
  },
};

export default ResultsViewerComponent;
