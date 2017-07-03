const ACCESS_KEY = 'svresult';

export class StateService {
  constructor($window) {
    'ngInject';

    this.window = $window;
  }

  setCurrentItem(item) {
    this.window.sessionStorage.setItem(ACCESS_KEY, JSON.stringify(item));
  }

  getStoredItem() {
    return JSON.parse(this.window.sessionStorage.getItem(ACCESS_KEY));
  }

  deleteStoredItem() {
    this.window.sessionStorage.removeItem(ACCESS_KEY);
  }
}

export default StateService;
