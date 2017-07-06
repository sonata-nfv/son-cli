import template from './controlmenu.html';
import { HIGHLIGHT_EVENT, MANAGEMENT_EVENT,
  LEVEL_EVENT, EXPAND_EVENT, MODAL_EVENT } from '../../services/event-strings';

export const ControlMenuComponent = {

  template,
  bindings: {
    fwgraphs: '<',
  },
  controller: class ControlMenuComponent {
    constructor(ValidatorService, $scope) {
      'ngInject';

      this.validatorService = ValidatorService;
      this.scope = $scope;
      this.mgmtToggled = true;
      this.collapseErrors = true;
      this.collapseWarns = true;
    }

    $onChanges(changesObj) {
      (changesObj.errors || changesObj.warnings) && (this.mgmtToggled = true);
    }

    toggleHighlight(id, toLight) {
      this.scope.$emit(HIGHLIGHT_EVENT.EMIT, { id, toLight, search: false });
    }

    toggleLevel(level) {
      this.scope.$emit(LEVEL_EVENT.EMIT, level);
    }

    toggleManagement(toShow) {
      this.scope.$emit(MANAGEMENT_EVENT.EMIT, toShow);
      this.mgmtToggled = toShow;
    }

    toggleExpand(toExpand) {
      this.scope.$emit(EXPAND_EVENT.EMIT, toExpand);
    }

    openModal() {
      this.scope.$emit(MODAL_EVENT, {});
    }
  },
};

export default ControlMenuComponent;
