import template from './modalbox.html';

export const ModalBoxComponent = {

  template,
  bindings: {
    isHidden: '<',
    onClose: '&',
    onIdChange: '&',
  },
  controller: class ModalBoxComponent {

    constructor(ValidatorService, $scope) {
      'ngInject';

      this.validatorService = ValidatorService;
      this.scope = $scope;
      this.prevReports = [];
      this.validation = {
        path: '',
        source: '',
        integrity: false,
        topology: false,
        syntax: false,
        file: null,
      };
      this.hasErrors = false;
      this.errorMessage = 'Validation couldn\'t complete...';
      this.type = '';
      this.strings = {
        options: ['project', 'package', 'service', 'function'],
        sources: ['local', 'url', 'embedded'],
      };
      this.scope.files = [];
    }

    $onInit() {
      this.validation.source = this.strings.sources[0];
      this.type = this.strings.options[0];

      this.scope.$watchCollection('files', (value) => {
        //  this.enableButton = (value.length > 0);
        if (value && value.length > 0) {
          this.validation.file = value[0];
        }
      });
    }

    $onChanges(changesObj) {
      if (changesObj.isHidden !== undefined) {
        if (!changesObj.isHidden.currenValue) {
          this.openModal();
        }
      }
    }

    openModal() {
      this.listReports();
    }

    listReports() {
      this.prevReports.length = 0;
      this.validatorService.getReports()
        .then((reports) => {
          Object.keys(reports).forEach((id) => {
            const repo = reports[id];
            this.prevReports.push({
              id,
              flags: ModalBoxComponent.translateFlags(repo),
              path: repo.path,
              type: repo.type,
            });
          });
        });
    }

    static translateFlags(repo) {
      const { topology, syntax, integrity } = repo;

      return `${syntax ? 'S' : ''}${integrity ? 'I' : ''}${topology ? 'T' : ''}`;
    }

    getTopology(id, path) {
      this.onIdChange({
        $event: { id, path },
      });

      this.closeModal();
    }

    validate(isValid) {
      console.log(this.validation)
      this.hasErrors = false;
      if (isValid) {
        this.validatorService.postValidate(this.type, this.validation)
          .then((response) => {
            this.getTopology(response.resource_id);
          })
          .catch(() => {
            this.hasErrors = true;
          });
      }
    }

    closeModal() {
      this.onClose();
    }
  },
};

export default ModalBoxComponent;
