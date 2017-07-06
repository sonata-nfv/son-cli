import template from './search-input.html';

export const SearchInputComponent = {
  template,
  bindings: {
    onSearch: '&',
  },
  controller: class SearchInputComponent {
    constructor($scope, $timeout) {
      'ngInject';

      this.scope = $scope;
      this.timeout = $timeout;
      this.searchTerm = '';
      this.searchTimer = undefined;
    }

    searchTopology() {
      this.timeout.cancel(this.searchTimer);
      this.searchTimer = this.timeout(() => {
        this.onSearch({
          $event: { search: this.searchTerm },
        });
      }, 750);
    }

    clearInput() {
      this.searchTerm = '';
      this.onSearch({
        $event: { search: this.searchTerm },
      });
    }
  },
};

export default SearchInputComponent;
